"""Access to the SQLite database.

The schema starts as schema-sqlite.sql (version 4, from the PHP site);
migrations.py brings it up to date when the app starts. Public pages run
with PRAGMA query_only, only the admin pages may write.
"""

import sqlite3
from pathlib import Path

from flask import Flask, current_app, g

from . import migrations

# the winner's row in scores has this score (schema v4)
WINNER = -9999


def connect(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, autocommit=True, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def get_db() -> sqlite3.Connection:
    """The connection for the current request."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, params).fetchone()


def read_only() -> None:
    """No writes on this connection (public pages)."""
    get_db().execute("PRAGMA query_only = ON")


def init_app(app: Flask) -> None:
    path = Path(app.config["DATABASE"])
    if not path.is_file():
        raise RuntimeError(f"database {path} not found")
    migrations.migrate(path)
    app.teardown_appcontext(close_db)
