"""Command line: flask --app unodb uno <command> (see README)."""

from pathlib import Path

import click
from flask import current_app
from flask.cli import AppGroup
from webauthn.helpers import generate_user_handle

from . import migrations
from .auth import ROLES, audit, create_invite, now
from .db import get_db, query, query_one

uno = AppGroup("uno", help="Users, invites and maintenance of the UNO database.")


def find_user(name: str):
    user = query_one("SELECT * FROM users WHERE name = ?", (name,))
    if user is None:
        raise click.ClickException(f"no user called {name!r} (see: flask uno users)")
    return user


@uno.command()
def migrate():
    """Bring the database schema up to date (also done at every start)."""
    applied = migrations.migrate(Path(current_app.config["DATABASE"]))
    click.echo(f"applied: {applied}" if applied else "schema is up to date")


@uno.command()
@click.argument("name")
@click.option(
    "--role",
    type=click.Choice(ROLES),
    default="contributor",
    show_default=True,
    help="Role of a new user (existing users keep theirs, see set-role).",
)
@click.option("--hours", default=48, show_default=True, help="Link valid for.")
def invite(name, role, hours):
    """Print a one-time link with which NAME sets up a passkey.

    Creates the user if needed. For an existing user this adds a passkey
    (e.g. a lost phone: the old passkeys keep working until removed).
    """
    db = get_db()
    user = query_one("SELECT * FROM users WHERE name = ?", (name,))
    if user is None:
        db.execute(
            "INSERT INTO users (name, role, webauthn_id) VALUES (?, ?, ?)",
            (name, role, generate_user_handle()),
        )
        user = find_user(name)
        audit("user created", name=name, role=role)
        click.echo(f"created user {name} ({role})")
    elif user["disabled"]:
        raise click.ClickException(
            f"{name}'s login was removed; enable it first: flask uno enable-user"
        )
    token = create_invite(user["id"], hours)
    audit("invite created", user=name, hours=hours)
    origin = current_app.config["ORIGIN"]
    click.echo(f"Link for {name} (valid {hours} hours, works once):")
    click.echo(f"{origin}/admin/invite/{token}")


@uno.command()
def users():
    """List all users."""
    rows = query(
        """SELECT users.*,
             (SELECT count(*) FROM credentials WHERE user_id = users.id) AS passkeys,
             (SELECT count(*) FROM session WHERE created_by = users.id
                AND deleted IS NULL) AS sessions,
             (SELECT count(*) FROM session WHERE created_by = users.id
                AND deleted IS NOT NULL) AS deleted
           FROM users ORDER BY name"""
    )
    if not rows:
        click.echo("no users yet (flask uno invite NAME --role admin)")
    for u in rows:
        state = f"login removed {u['disabled']}" if u["disabled"] else "active"
        click.echo(
            f"{u['name']:20} {u['role']:12} passkeys: {u['passkeys']}  "
            f"sessions: {u['sessions']} (+{u['deleted']} deleted)  {state}"
        )


@uno.command("set-role")
@click.argument("name")
@click.argument("role", type=click.Choice(ROLES))
def set_role(name, role):
    """Change the role of a user."""
    user = find_user(name)
    get_db().execute("UPDATE users SET role = ? WHERE id = ?", (role, user["id"]))
    audit("role changed", user=name, before=user["role"], after=role)
    click.echo(f"{name}: {user['role']} -> {role}")


@uno.command("claim-sessions")
@click.argument("name")
def claim_sessions(name):
    """Make NAME the owner of all sessions without one (the old data)."""
    user = find_user(name)
    count = (
        get_db()
        .execute(
            "UPDATE session SET created_by = ? WHERE created_by IS NULL",
            (user["id"],),
        )
        .rowcount
    )
    audit("sessions claimed", user=name, sessions=count)
    click.echo(f"{count} sessions now belong to {name}")


@uno.command("remove-user")
@click.argument("name")
@click.option(
    "--delete-sessions",
    is_flag=True,
    help="Also delete all sessions NAME entered (soft delete, can be restored).",
)
def remove_user(name, delete_sessions):
    """Remove the login of NAME (passkeys and open invites).

    The user's sessions stay unless --delete-sessions is given. Nothing is
    really deleted from the database: restore-sessions and enable-user undo
    this.
    """
    user = find_user(name)
    db = get_db()
    db.execute("DELETE FROM credentials WHERE user_id = ?", (user["id"],))
    db.execute(
        "UPDATE invites SET used = ? WHERE user_id = ? AND used IS NULL",
        (now(), user["id"]),
    )
    db.execute(
        "UPDATE users SET disabled = ? WHERE id = ? AND disabled IS NULL",
        (now(), user["id"]),
    )
    audit("login removed", user=name)
    click.echo(f"login of {name} removed (passkeys deleted, invites cancelled)")
    if delete_sessions:
        _delete_sessions(user)


def _delete_sessions(user):
    ids = [
        r["id"]
        for r in query(
            "SELECT id FROM session WHERE created_by = ? AND deleted IS NULL",
            (user["id"],),
        )
    ]
    get_db().execute(
        "UPDATE session SET deleted = ? WHERE created_by = ? AND deleted IS NULL",
        (now(), user["id"]),
    )
    audit("sessions deleted", user=user["name"], sessions=ids)
    click.echo(f"{len(ids)} sessions of {user['name']} deleted (restore-sessions)")


@uno.command("delete-sessions")
@click.argument("name")
def delete_sessions(name):
    """Delete all sessions NAME entered (soft delete, can be restored)."""
    _delete_sessions(find_user(name))


@uno.command("restore-sessions")
@click.argument("name")
def restore_sessions(name):
    """Undo delete-sessions / remove-user --delete-sessions for NAME."""
    user = find_user(name)
    count = (
        get_db()
        .execute(
            "UPDATE session SET deleted = NULL WHERE created_by = ?"
            " AND deleted IS NOT NULL",
            (user["id"],),
        )
        .rowcount
    )
    audit("sessions restored", user=name, sessions=count)
    click.echo(f"{count} sessions of {name} restored")


@uno.command("enable-user")
@click.argument("name")
def enable_user(name):
    """Allow NAME to log in again (then send a new invite)."""
    user = find_user(name)
    get_db().execute("UPDATE users SET disabled = NULL WHERE id = ?", (user["id"],))
    audit("login enabled", user=name)
    click.echo(f"{name} enabled; send a new link: flask uno invite {name}")
