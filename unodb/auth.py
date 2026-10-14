"""Login with passkeys (WebAuthn), users, roles and invites.

There are no passwords. A user gets a one-time invite link from the
command line (flask uno invite), sets up a passkey with it and logs in
with that passkey from then on. Logged in users can add more passkeys
(e.g. phone and laptop) and remove them again.

Roles: admin (everything), editor (edit any session), contributor (enter
sessions, edit only their own).

Every POST needs the CSRF token of the session (form field "csrf" or
header X-CSRF-Token) and, if the browser sends one, an Origin header that
matches ORIGIN.
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from functools import wraps

import webauthn
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .db import get_db, query, query_one

ROLES = ("admin", "editor", "contributor")
RP_NAME = "The UNO database"

admin = Blueprint("admin", __name__, url_prefix="/admin")


# --- helpers ---------------------------------------------------------------


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def audit(action: str, user_id: int | None = None, **details) -> None:
    """Record a change; user_id None means the command line."""
    get_db().execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, json.dumps(details, default=str)),
    )


def create_invite(user_id: int, hours: float) -> str:
    """A new one-time invite token for the user (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=hours)
    get_db().execute(
        "INSERT INTO invites (token_hash, user_id, expires) VALUES (?, ?, ?)",
        (token_hash(token), user_id, expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    return token


def valid_invite(token: str):
    """The invite row joined with its user, or None if not usable."""
    return query_one(
        """SELECT invites.token_hash, users.id AS user_id, users.name
           FROM invites JOIN users ON users.id = invites.user_id
           WHERE invites.token_hash = ? AND invites.used IS NULL
             AND invites.expires > ? AND users.disabled IS NULL""",
        (token_hash(token), now()),
    )


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def log_in(user_id: int) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    csrf_token()


def load_user() -> None:
    """g.user: the logged in user (or None), for every request."""
    g.user = None
    if "user_id" in session:
        g.user = query_one(
            "SELECT * FROM users WHERE id = ? AND disabled IS NULL",
            (session["user_id"],),
        )
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped


def rp_id() -> str:
    return current_app.config["RP_ID"]


def origin() -> str:
    return current_app.config["ORIGIN"]


@admin.before_request
def check_post():
    if request.method != "POST":
        return
    sent_origin = request.headers.get("Origin")
    if sent_origin is not None and sent_origin != origin():
        abort(403)
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf")
    if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
        abort(403)


# --- pages -----------------------------------------------------------------


@admin.route("/")
@login_required
def start():
    passkeys = query(
        """SELECT id, name, created, last_used FROM credentials
           WHERE user_id = ? ORDER BY created""",
        (g.user["id"],),
    )
    return render_template(
        "admin/start.html",
        passkeys=[dict(p, key=bytes_to_base64url(p["id"])) for p in passkeys],
        variants=query(
            """SELECT variations.id, variations.name, variations.short,
                      variations.created_by, variations.description,
                      users.name AS author,
                      (SELECT count(*) FROM session WHERE session.deleted IS NULL
                         AND session.variation = variations.id) AS sessions
               FROM variations LEFT JOIN users ON users.id = variations.created_by
               ORDER BY sessions DESC, variations.name"""
        ),
        rename=request.args.get("rename"),
    )


@admin.route("/login")
def login():
    if g.user is not None:
        return redirect(url_for("admin.start"))
    csrf_token()
    return render_template("admin/login.html")


@admin.route("/invite/<token>")
def invite(token):
    row = valid_invite(token)
    if row is None:
        return render_template("admin/invite.html", invite=None), 404
    csrf_token()
    return render_template("admin/invite.html", invite=row, token=token)


@admin.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("stats.index"))


@admin.post("/passkeys/<key>/rename")
@login_required
def rename_passkey(key):
    name = " ".join((request.form.get("name") or "").split())[:60] or None
    changed = (
        get_db()
        .execute(
            "UPDATE credentials SET name = ? WHERE id = ? AND user_id = ?",
            (name, webauthn.base64url_to_bytes(key), g.user["id"]),
        )
        .rowcount
    )
    if not changed:
        abort(404)
    audit("passkey renamed", g.user["id"], credential=key, name=name)
    return redirect(url_for("admin.start"))


@admin.post("/passkeys/<key>/delete")
@login_required
def delete_passkey(key):
    credential_id = webauthn.base64url_to_bytes(key)
    count = query_one(
        "SELECT count(*) FROM credentials WHERE user_id = ?", (g.user["id"],)
    )[0]
    if count <= 1:
        flash("This is your only passkey; without it you couldn't log in again.")
        return redirect(url_for("admin.start"))
    get_db().execute(
        "DELETE FROM credentials WHERE id = ? AND user_id = ?",
        (credential_id, g.user["id"]),
    )
    audit("passkey removed", g.user["id"], credential=key)
    return redirect(url_for("admin.start"))


# --- WebAuthn: registration --------------------------------------------------


@admin.post("/register/options")
def register_options():
    """Options for a new passkey: with an invite token, or logged in."""
    data = request.get_json(silent=True) or {}
    if g.user is not None:
        user_id, invite_hash = g.user["id"], None
    else:
        row = valid_invite(data.get("token", ""))
        if row is None:
            return jsonify(error="This invite link is not valid (anymore)."), 400
        user_id, invite_hash = row["user_id"], row["token_hash"]
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    existing = query("SELECT id FROM credentials WHERE user_id = ?", (user_id,))
    options = webauthn.generate_registration_options(
        rp_id=rp_id(),
        rp_name=RP_NAME,
        user_id=user["webauthn_id"],
        user_name=user["name"],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=c["id"]) for c in existing
        ],
    )
    session["registration"] = {
        "challenge": bytes_to_base64url(options.challenge),
        "user_id": user_id,
        "invite": invite_hash,
        "name": (data.get("name") or "").strip()[:60] or None,
    }
    return current_app.response_class(
        webauthn.options_to_json(options), mimetype="application/json"
    )


@admin.post("/register/verify")
def register_verify():
    state = session.pop("registration", None)
    if state is None:
        return jsonify(error="Please start again."), 400
    if state["invite"] is not None:
        # the invite must still be unused (checked again, it's one-time)
        row = query_one(
            "SELECT used, expires FROM invites WHERE token_hash = ?",
            (state["invite"],),
        )
        if row is None or row["used"] or row["expires"] <= now():
            return jsonify(error="This invite link is not valid (anymore)."), 400
    elif g.user is None or g.user["id"] != state["user_id"]:
        return jsonify(error="Please log in again."), 400
    try:
        verified = webauthn.verify_registration_response(
            credential=request.get_data(as_text=True),
            expected_challenge=webauthn.base64url_to_bytes(state["challenge"]),
            expected_rp_id=rp_id(),
            expected_origin=origin(),
        )
    except InvalidRegistrationResponse as error:
        return jsonify(error=f"The passkey could not be verified: {error}"), 400

    db = get_db()
    db.execute(
        """INSERT INTO credentials (id, user_id, public_key, sign_count, name)
           VALUES (?, ?, ?, ?, ?)""",
        (
            verified.credential_id,
            state["user_id"],
            verified.credential_public_key,
            verified.sign_count,
            state["name"],
        ),
    )
    if state["invite"] is not None:
        db.execute(
            "UPDATE invites SET used = ? WHERE token_hash = ?", (now(), state["invite"])
        )
    audit(
        "passkey added",
        state["user_id"],
        credential=bytes_to_base64url(verified.credential_id),
        via="invite" if state["invite"] else "logged in",
    )
    log_in(state["user_id"])
    return jsonify(ok=True, next=url_for("admin.start"))


# --- WebAuthn: login ---------------------------------------------------------


@admin.post("/login/options")
def login_options():
    # discoverable credentials: the browser offers the passkeys it has
    options = webauthn.generate_authentication_options(
        rp_id=rp_id(), user_verification=UserVerificationRequirement.PREFERRED
    )
    session["authentication"] = bytes_to_base64url(options.challenge)
    return current_app.response_class(
        webauthn.options_to_json(options), mimetype="application/json"
    )


@admin.post("/login/verify")
def login_verify():
    challenge = session.pop("authentication", None)
    data = request.get_json(silent=True) or {}
    if challenge is None or "rawId" not in data:
        return jsonify(error="Please start again."), 400
    try:
        credential_id = webauthn.base64url_to_bytes(data["rawId"])
    except ValueError:
        return jsonify(error="Unknown passkey."), 400
    row = query_one(
        """SELECT credentials.*, users.disabled FROM credentials
           JOIN users ON users.id = credentials.user_id WHERE credentials.id = ?""",
        (credential_id,),
    )
    if row is None or row["disabled"]:
        return jsonify(error="This passkey is not registered here."), 400
    try:
        verified = webauthn.verify_authentication_response(
            credential=data,
            expected_challenge=webauthn.base64url_to_bytes(challenge),
            expected_rp_id=rp_id(),
            expected_origin=origin(),
            credential_public_key=row["public_key"],
            credential_current_sign_count=row["sign_count"],
        )
    except InvalidAuthenticationResponse as error:
        return jsonify(error=f"The passkey could not be verified: {error}"), 400
    get_db().execute(
        "UPDATE credentials SET sign_count = ?, last_used = ? WHERE id = ?",
        (verified.new_sign_count, now(), credential_id),
    )
    log_in(row["user_id"])
    return jsonify(ok=True, next=url_for("admin.start"))


def init_app(app) -> None:
    app.before_request(load_user)
    app.register_blueprint(admin)

    @app.context_processor
    def auth_context():
        return {"current_user": g.get("user"), "csrf_token": csrf_token}
