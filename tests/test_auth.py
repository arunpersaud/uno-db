import re
import sqlite3

import pytest

from unodb.auth import token_hash
from unodb.db import get_db


def cli(app, *args):
    result = app.test_cli_runner().invoke(args=["uno", *args])
    return result


def invite(app, name="Arun", role="admin"):
    """Create a user with an invite; returns the token from the printed link."""
    result = cli(app, "invite", name, "--role", role)
    assert result.exit_code == 0, result.output
    return re.search(r"/admin/invite/(\S+)", result.output)[1]


def user_id(app, name):
    with app.app_context():
        return (
            get_db()
            .execute("SELECT id FROM users WHERE name = ?", (name,))
            .fetchone()[0]
        )


def log_in(client, uid):
    with client.session_transaction() as session:
        session["user_id"] = uid
        session["csrf"] = "test-token"


def test_migrations(app, database):
    db = sqlite3.connect(database)
    assert db.execute("SELECT version FROM version").fetchone()[0] == 6
    columns = [r[1] for r in db.execute("PRAGMA table_info(session)")]
    assert "created_by" in columns and "deleted" in columns
    # a copy of the v4 database was made first
    assert list((database.parent / "backups").glob("uno-v4-*.sqlite"))


def test_migration_runs_once(database):
    from pathlib import Path

    from unodb import migrations

    assert migrations.migrate(Path(database)) == [5, 6]
    assert migrations.migrate(Path(database)) == []


def test_invite_creates_user(app):
    result = cli(app, "invite", "Arun", "--role", "admin")
    assert "created user Arun (admin)" in result.output
    assert "valid 48 hours, works once" in result.output
    token = re.search(r"http://localhost:5000/admin/invite/(\S+)", result.output)[1]
    with app.app_context():
        row = (
            get_db()
            .execute(
                "SELECT users.role FROM invites"
                " JOIN users ON users.id = invites.user_id WHERE token_hash = ?",
                (token_hash(token),),
            )
            .fetchone()
        )
    assert row["role"] == "admin"


def test_two_admins(app):
    invite(app, "Arun")
    invite(app, "Sean")
    output = cli(app, "users").output
    assert re.search(r"Arun\s+admin", output)
    assert re.search(r"Sean\s+admin", output)


def test_invite_page(app, client):
    token = invite(app)
    html = client.get(f"/admin/invite/{token}").text
    assert "Welcome, Arun" in html
    assert 'name="csrf-token"' in html
    assert client.get("/admin/invite/wrong").status_code == 404


def test_used_or_expired_invite(app, client):
    token = invite(app)
    with app.app_context():
        get_db().execute("UPDATE invites SET used = '2026-01-01 00:00:00'")
    assert client.get(f"/admin/invite/{token}").status_code == 404

    token = invite(app)
    with app.app_context():
        get_db().execute("UPDATE invites SET expires = '2000-01-01 00:00:00'")
    assert client.get(f"/admin/invite/{token}").status_code == 404


def post_json(client, url, body, token="test-token", origin="http://localhost:5000"):
    headers = {"X-CSRF-Token": token}
    if origin:
        headers["Origin"] = origin
    return client.post(url, json=body, headers=headers)


def test_register_options(app, client):
    token = invite(app)
    client.get(f"/admin/invite/{token}")  # sets the CSRF token
    with client.session_transaction() as session:
        csrf = session["csrf"]
    response = post_json(client, "/admin/register/options", {"token": token}, csrf)
    assert response.status_code == 200
    options = response.get_json()
    assert options["rp"]["id"] == "localhost"
    assert options["user"]["name"] == "Arun"
    assert options["authenticatorSelection"]["residentKey"] == "required"


def test_register_options_needs_invite(app, client):
    log_in(client, None)
    with client.session_transaction() as session:
        session.pop("user_id")
    response = post_json(client, "/admin/register/options", {"token": "wrong"})
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("token", "origin"),
    [("wrong", "http://localhost:5000"), ("test-token", "https://evil.example")],
)
def test_post_checks_csrf_and_origin(app, client, token, origin):
    invite(app)
    log_in(client, user_id(app, "Arun"))
    response = post_json(client, "/admin/login/options", {}, token, origin)
    assert response.status_code == 403


def test_login_options(app, client):
    client.get("/admin/login")
    with client.session_transaction() as session:
        csrf = session["csrf"]
    options = post_json(client, "/admin/login/options", {}, csrf).get_json()
    assert options["rpId"] == "localhost"
    assert options.get("allowCredentials", []) == []  # browser offers passkeys


def test_login_verify_unknown_passkey(app, client):
    client.get("/admin/login")
    with client.session_transaction() as session:
        csrf = session["csrf"]
    post_json(client, "/admin/login/options", {}, csrf)
    response = post_json(client, "/admin/login/verify", {"rawId": "AAAA"}, csrf)
    assert response.status_code == 400
    assert "not registered" in response.get_json()["error"]


def test_start_needs_login(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert response.location == "/admin/login"


def test_start_page(app, client):
    invite(app, "Joe Miller", "contributor")
    log_in(client, user_id(app, "Joe Miller"))
    html = client.get("/admin/").text
    assert "Hello Joe Miller" in html
    assert "logged in as contributor" in html
    assert "first and last name" in html
    assert ">Admin</a>" in html  # nav link when logged in


def test_cannot_remove_last_passkey(app, client):
    invite(app)
    uid = user_id(app, "Arun")
    with app.app_context():
        get_db().execute(
            "INSERT INTO credentials (id, user_id, public_key, sign_count)"
            " VALUES (x'01', ?, x'00', 0)",
            (uid,),
        )
    log_in(client, uid)
    response = client.post("/admin/passkeys/AQ/delete", data={"csrf": "test-token"})
    assert response.status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM credentials").fetchone()[0] == 1


def test_logout(app, client):
    invite(app)
    log_in(client, user_id(app, "Arun"))
    client.post("/admin/logout", data={"csrf": "test-token"})
    assert client.get("/admin/").status_code == 302


def test_disabled_user_is_logged_out(app, client):
    invite(app, "Spammer", "contributor")
    log_in(client, user_id(app, "Spammer"))
    assert cli(app, "remove-user", "Spammer").exit_code == 0
    assert client.get("/admin/").status_code == 302


def test_remove_user_and_restore_sessions(app, client):
    invite(app, "Spammer", "contributor")
    # the spammer entered sessions 2 and 3 (both on 2004-06-01)
    with app.app_context():
        get_db().execute(
            "UPDATE session SET created_by = ? WHERE id IN (2, 3)",
            (user_id(app, "Spammer"),),
        )
    assert "4 games in 3 sessions" in client.get("/").text

    result = cli(app, "remove-user", "Spammer", "--delete-sessions")
    assert result.exit_code == 0, result.output
    assert "2 sessions of Spammer deleted" in result.output
    assert "2 games in 1 sessions" in client.get("/").text
    assert client.get("/session/2004-06-01").status_code == 404
    assert re.search(
        r"Spammer\s+contributor.*sessions: 0 \(\+2 deleted\)  login removed",
        cli(app, "users").output,
    )

    # an invite for a removed user needs enable-user first
    assert cli(app, "invite", "Spammer").exit_code != 0

    assert (
        "2 sessions of Spammer restored"
        in cli(app, "restore-sessions", "Spammer").output
    )
    assert "4 games in 3 sessions" in client.get("/").text
    assert cli(app, "enable-user", "Spammer").exit_code == 0
    assert cli(app, "invite", "Spammer").exit_code == 0


def test_claim_sessions(app):
    invite(app)
    result = cli(app, "claim-sessions", "Arun")
    assert "3 sessions now belong to Arun" in result.output
    assert "0 sessions now belong" in cli(app, "claim-sessions", "Arun").output


def test_set_role(app):
    invite(app, "Joe Miller", "contributor")
    assert (
        "contributor -> editor" in cli(app, "set-role", "Joe Miller", "editor").output
    )
    assert cli(app, "set-role", "Nobody", "editor").exit_code != 0


def test_audit_log(app):
    invite(app, "Joe Miller", "contributor")
    cli(app, "set-role", "Joe Miller", "editor")
    with app.app_context():
        actions = [
            r[0] for r in get_db().execute("SELECT action FROM audit_log ORDER BY id")
        ]
    assert actions == ["user created", "invite created", "role changed"]


def test_rename_passkey(app, client):
    invite(app)
    uid = user_id(app, "Arun")
    with app.app_context():
        get_db().execute(
            "INSERT INTO credentials (id, user_id, public_key, sign_count, name)"
            " VALUES (x'01', ?, x'00', 0, 'old')",
            (uid,),
        )
    log_in(client, uid)
    html = client.get("/admin/?rename=AQ").text
    assert 'value="old"' in html
    client.post(
        "/admin/passkeys/AQ/rename", data={"csrf": "test-token", "name": " my  phone "}
    )
    with app.app_context():
        assert (
            get_db().execute("SELECT name FROM credentials").fetchone()[0] == "my phone"
        )
    assert "my phone" in client.get("/admin/").text

    # someone else's passkey: not found
    invite(app, "Eve Other", "contributor")
    log_in(client, user_id(app, "Eve Other"))
    response = client.post(
        "/admin/passkeys/AQ/rename", data={"csrf": "test-token", "name": "x"}
    )
    assert response.status_code == 404
