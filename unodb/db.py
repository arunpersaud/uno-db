"""Access to the SQLite database (schema: schema-sqlite.sql, version 4).

The database is shared with the old PHP site for now, so the app opens it
read-only until the admin pages exist.
"""

import sqlite3
from pathlib import Path

from flask import Flask, current_app, g

# the winner's row in scores has this score (schema v4)
WINNER = -9999


def connect(path: str | Path) -> sqlite3.Connection:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    db = sqlite3.connect(uri, uri=True, autocommit=True, timeout=10)
    db.row_factory = sqlite3.Row
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


def init_app(app: Flask) -> None:
    if not Path(app.config["DATABASE"]).is_file():
        raise RuntimeError(f"database {app.config['DATABASE']} not found")
    app.teardown_appcontext(close_db)
