"""Schema migrations, applied when the app starts.

The version table holds the schema version (4 = the PHP site's schema).
Before a migration the database is copied to backups/ next to it. A lock
file keeps several gunicorn workers from migrating at the same time.
"""

import fcntl
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS = {
    # users with passkeys, roles, invites, audit log; sessions get an owner
    # and a soft delete
    5: """
CREATE TABLE users (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
  role            TEXT NOT NULL CHECK (role IN ('admin', 'editor', 'contributor')),
  webauthn_id     BLOB NOT NULL UNIQUE,  -- user handle stored in the passkeys
  default_variant INTEGER REFERENCES variations(id),
  created         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  disabled        TEXT                   -- time the login was removed
);
CREATE TABLE credentials (
  id          BLOB PRIMARY KEY,           -- credential id from the passkey
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  public_key  BLOB NOT NULL,
  sign_count  INTEGER NOT NULL,
  name        TEXT,
  created     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used   TEXT
);
CREATE INDEX credentials_user ON credentials(user_id);
CREATE TABLE invites (
  token_hash  TEXT PRIMARY KEY,           -- sha256 of the token in the link
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires     TEXT NOT NULL,
  used        TEXT
);
CREATE TABLE audit_log (
  id          INTEGER PRIMARY KEY,
  time        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id     INTEGER REFERENCES users(id),  -- NULL: command line
  action      TEXT NOT NULL,
  details     TEXT                           -- JSON
);
ALTER TABLE session ADD COLUMN created_by INTEGER REFERENCES users(id);
ALTER TABLE session ADD COLUMN deleted TEXT;  -- soft delete: time
CREATE INDEX session_created_by ON session(created_by);
""",
    # score entry: players of a session in seating order (also before the
    # first game), who created players/locations/game types, rules texts,
    # unique names
    6: """
CREATE TABLE session_players (
  session     INTEGER NOT NULL REFERENCES session(id),
  player      INTEGER NOT NULL REFERENCES players(id),
  seat        INTEGER NOT NULL,  -- 0, 1, ... (scores.position of new games)
  PRIMARY KEY (session, player)
);
-- seats of the old sessions: from each player's first game in the session
INSERT INTO session_players (session, player, seat)
SELECT games.session, scores.player, scores.position
FROM scores JOIN games ON games.id = scores.game
WHERE games.id = (
  SELECT min(g2.id) FROM games g2 JOIN scores s2 ON s2.game = g2.id
  WHERE g2.session = games.session AND s2.player = scores.player
);
ALTER TABLE players ADD COLUMN created_by INTEGER REFERENCES users(id);
ALTER TABLE locations ADD COLUMN created_by INTEGER REFERENCES users(id);
ALTER TABLE variations ADD COLUMN created_by INTEGER REFERENCES users(id);
ALTER TABLE variations ADD COLUMN description TEXT;  -- the rules
CREATE UNIQUE INDEX players_name ON players(name COLLATE NOCASE);
CREATE UNIQUE INDEX locations_name ON locations(name COLLATE NOCASE);
CREATE UNIQUE INDEX variations_short ON variations(short COLLATE NOCASE);
CREATE UNIQUE INDEX scores_game_player ON scores(game, player);
""",
}

LATEST = max(MIGRATIONS)


def version(db: sqlite3.Connection) -> int:
    return db.execute("SELECT version FROM version").fetchone()[0]


def backup(db: sqlite3.Connection, path: Path, label: str) -> Path:
    """Consistent copy of the database into backups/ next to it."""
    folder = path.parent / "backups"
    folder.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = folder / f"{path.stem}-{label}-{stamp}.sqlite"
    with closing(sqlite3.connect(target)) as copy:
        db.backup(copy)
    return target


def migrate(path: Path) -> list[int]:
    """Apply missing migrations; returns the versions applied."""
    applied = []
    with open(path.with_name(path.name + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with closing(sqlite3.connect(path, autocommit=True)) as db:
            current = version(db)
            if current >= LATEST:
                return applied
            backup(db, path, f"v{current}")
            for target in range(current + 1, LATEST + 1):
                db.executescript(
                    "BEGIN;\n"
                    + MIGRATIONS[target]
                    + f"\nUPDATE version SET version = {target};\nCOMMIT;"
                )
                applied.append(target)
    return applied
