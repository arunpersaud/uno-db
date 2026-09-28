-- SQLite schema for uno-db (converted from the MySQL schema, version 4)
--
-- Differences to MySQL:
--  * locations.coordinates: MySQL POINT -> TEXT "x y"; POINT()/X()/Y() are
--    provided as PHP functions in include/functions.php
--  * MySQL filled in CURRENT_TIMESTAMP when NULL was inserted into a
--    TIMESTAMP column; the code relies on that, so triggers emulate it.
--    MySQL's '0000-00-00 00:00:00' became NULL.

PRAGMA journal_mode = WAL;

CREATE TABLE backup (
  id          INTEGER PRIMARY KEY,
  create_date TEXT,
  content     TEXT
);

CREATE TABLE games (
  id                  INTEGER PRIMARY KEY,
  session             INTEGER,
  end_with_black_card INTEGER
);

CREATE TABLE locations (
  id          INTEGER PRIMARY KEY,
  create_date TEXT,
  name        TEXT,
  coordinates TEXT
);

CREATE TABLE players (
  id          INTEGER PRIMARY KEY,
  create_date TEXT,
  name        TEXT
);

CREATE TABLE scores (
  id       INTEGER PRIMARY KEY,
  game     INTEGER,
  player   INTEGER,
  score    INTEGER,
  position INTEGER
);

CREATE TABLE session (
  id                INTEGER PRIMARY KEY,
  date              TEXT,
  location_id       INTEGER NOT NULL,
  number_of_players INTEGER,
  create_date       TEXT,
  variation         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE variations (
  id          INTEGER PRIMARY KEY,
  create_date TEXT,
  name        TEXT,
  short       TEXT
);

CREATE TABLE version (
  version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX scores_game   ON scores(game);
CREATE INDEX scores_player ON scores(player);
CREATE INDEX games_session ON games(session);

CREATE TRIGGER backup_ts     AFTER INSERT ON backup     WHEN NEW.create_date IS NULL
  BEGIN UPDATE backup     SET create_date = CURRENT_TIMESTAMP WHERE id = NEW.id; END;
CREATE TRIGGER locations_ts  AFTER INSERT ON locations  WHEN NEW.create_date IS NULL
  BEGIN UPDATE locations  SET create_date = CURRENT_TIMESTAMP WHERE id = NEW.id; END;
CREATE TRIGGER players_ts    AFTER INSERT ON players    WHEN NEW.create_date IS NULL
  BEGIN UPDATE players    SET create_date = CURRENT_TIMESTAMP WHERE id = NEW.id; END;
CREATE TRIGGER session_ts    AFTER INSERT ON session    WHEN NEW.create_date IS NULL
  BEGIN UPDATE session    SET create_date = CURRENT_TIMESTAMP WHERE id = NEW.id; END;
CREATE TRIGGER variations_ts AFTER INSERT ON variations WHEN NEW.create_date IS NULL
  BEGIN UPDATE variations SET create_date = CURRENT_TIMESTAMP WHERE id = NEW.id; END;
