import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from unodb import create_app

SCHEMA = Path(__file__).parent.parent / "schema-sqlite.sql"

# three sessions, the last two on the same day; in session 1 Ann wins
# game 1, Bob game 2
DATA = """
INSERT INTO version VALUES (4);
INSERT INTO variations (id, name, short) VALUES (1, 'Uno default', 'Uno');
INSERT INTO locations (id, name) VALUES (1, 'Berkeley'), (2, 'Lodi');
INSERT INTO players (id, name) VALUES (1, 'Ann'), (2, 'Bob'), (3, 'Cy Young');
INSERT INTO session (id, date, location_id, number_of_players, variation)
    VALUES (1, '2004-05-28', 1, 3, 1), (2, '2004-06-01', 1, 2, 1),
           (3, '2004-06-01', 2, 2, 1);
INSERT INTO games (id, session, end_with_black_card)
    VALUES (1, 1, 0), (2, 1, 1), (3, 2, 0), (4, 3, 0);
INSERT INTO scores (game, player, score, position) VALUES
    (1, 1, -9999, 0), (1, 2, 12, 1), (1, 3, 30, 2),
    (2, 1, 5, 0), (2, 2, -9999, 1), (2, 3, 50, 2),
    (3, 1, -9999, 0), (3, 3, 7, 1),
    (4, 2, -9999, 0), (4, 3, 20, 1);
"""


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "uno.sqlite"
    with closing(sqlite3.connect(path)) as db:
        db.executescript(SCHEMA.read_text())
        db.executescript(DATA)
    return path


@pytest.fixture
def app(database):
    return create_app({"TESTING": True, "DATABASE": database})


@pytest.fixture
def client(app):
    return app.test_client()
