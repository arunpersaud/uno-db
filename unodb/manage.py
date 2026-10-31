"""Admin-only pages: users and roles, renaming players and locations, audit log.

Every view here uses @admin_required (login AND role admin, else 403).
Making someone an admin, or changing an admin, is deliberately not possible
on these pages, only on the command line (flask uno set-role), so it needs
access to the server: a stolen admin session can't hand out more admin
rights.
"""

import json

from flask import abort, g, redirect, render_template, request, url_for

from .auth import ROLES, admin, admin_required, audit
from .db import query, query_one
from .entry import clean, transaction
from .views import slug

GRANTABLE = tuple(role for role in ROLES if role != "admin")
PAGE = 100


# --- users and roles ---------------------------------------------------------


@admin.route("/users")
@admin_required
def users():
    rows = query(
        """SELECT users.id, users.name, users.role, users.disabled, users.created,
                  (SELECT count(*) FROM credentials WHERE user_id = users.id)
                    AS passkeys,
                  (SELECT count(*) FROM session WHERE session.created_by = users.id
                     AND session.deleted IS NULL) AS sessions
           FROM users ORDER BY users.name"""
    )
    return render_template("admin/users.html", users=rows, grantable=GRANTABLE)


@admin.post("/users/<int:user_id>/role")
@admin_required
def set_role(user_id):
    target = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if target is None:
        abort(404)
    role = request.form.get("role")
    if role not in GRANTABLE:
        abort(403 if role == "admin" else 400)
    if target["role"] == "admin":
        abort(403)  # admins are changed on the command line only
    if role != target["role"]:
        with transaction() as db:
            db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            audit(
                "role changed",
                g.user["id"],
                user=target["name"],
                before=target["role"],
                after=role,
            )
    return redirect(url_for("admin.users"), 303)


# --- renaming players and locations -------------------------------------------


def name_problem(name: str, table: str, item_id: int) -> str | None:
    """Why NAME can't be the new name of this player or location, or None."""
    if not 2 <= len(name) <= 60:
        return f"{name!r}: names need 2 to 60 characters."
    for row in query(f"SELECT id, name FROM {table} WHERE id != ?", (item_id,)):  # noqa: S608
        same = (
            slug(row["name"]) == slug(name)
            if table == "players"
            else row["name"].lower() == name.lower()
        )
        if same:
            return f"{name!r} is already taken (by {row['name']!r})."
    return None


def rename(table: str, item_id: int, what: str):
    row = query_one(f"SELECT * FROM {table} WHERE id = ?", (item_id,))  # noqa: S608
    if row is None:
        abort(404)
    name = clean(request.form.get("name"))
    if name == row["name"]:
        return redirect(url_for("admin.people"), 303)
    if problem := name_problem(name, table, item_id):
        return people(problems=[problem], status=400)
    with transaction() as db:
        db.execute(f"UPDATE {table} SET name = ? WHERE id = ?", (name, item_id))  # noqa: S608
        audit(
            f"{what} renamed", g.user["id"], id=item_id, before=row["name"], after=name
        )
    return redirect(url_for("admin.people"), 303)


@admin.route("/people")
@admin_required
def people(problems=(), status=200):
    return (
        render_template(
            "admin/people.html",
            problems=problems,
            players=query(
                """SELECT players.id, players.name,
                          (SELECT count(*) FROM scores WHERE scores.player = players.id)
                            AS scores
                   FROM players ORDER BY players.name COLLATE NOCASE"""
            ),
            locations=query(
                """SELECT locations.id, locations.name,
                          (SELECT count(*) FROM session
                           WHERE session.location_id = locations.id
                             AND session.deleted IS NULL) AS sessions
                   FROM locations ORDER BY locations.name COLLATE NOCASE"""
            ),
        ),
        status,
    )


@admin.post("/players/<int:player_id>/rename")
@admin_required
def rename_player(player_id):
    return rename("players", player_id, "player")


@admin.post("/locations/<int:location_id>/rename")
@admin_required
def rename_location(location_id):
    return rename("locations", location_id, "location")


# --- audit log -----------------------------------------------------------------


@admin.route("/audit")
@admin_required
def audit_log():
    action = request.args.get("action", "")
    page = max(request.args.get("page", 1, type=int), 1)
    where, params = ("WHERE audit_log.action = ?", [action]) if action else ("", [])
    rows = query(
        f"""SELECT audit_log.id, audit_log.time, audit_log.action, audit_log.details,
                   users.name AS user
            FROM audit_log LEFT JOIN users ON users.id = audit_log.user_id
            {where} ORDER BY audit_log.id DESC LIMIT ? OFFSET ?""",  # noqa: S608
        (*params, PAGE + 1, (page - 1) * PAGE),
    )
    entries = [dict(row, details=_pretty(row["details"])) for row in rows[:PAGE]]
    return render_template(
        "admin/audit.html",
        entries=entries,
        actions=[
            r[0] for r in query("SELECT DISTINCT action FROM audit_log ORDER BY 1")
        ],
        action=action,
        page=page,
        more=len(rows) > PAGE,
    )


def _pretty(details: str | None) -> str:
    try:
        data = json.loads(details or "{}")
    except ValueError:
        return details or ""
    return ", ".join(f"{k}: {v}" for k, v in data.items())
