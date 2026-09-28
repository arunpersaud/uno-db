# uno-db

Web interface for keeping UNO game statistics: players, sessions, games and
scores, with per-player statistics, moving averages and charts.

Extracted (with history) from the `uno-db/` directory of
[UNO-darmstadt](https://sourceforge.net/p/uno-darmstadt/code/) (2009-2017).

## Status

- `main`: PHP 8 + SQLite. The MySQL-specific SQL functions the queries use
  (`IF`, `STD`, `POINT`, `X`, `Y`) are provided as SQLite user functions in
  `include/functions.php`, so the queries themselves are unchanged.
- tag `mysql-final`: last MySQL version.
- Planned: rewrite in Python (Flask + Jinja2) on the same SQLite database.

## Setup

1. Create the database, either empty

       sqlite3 uno.sqlite < schema-sqlite.sql

   or from a MySQL dump (made with `--skip-extended-insert`)

       tools/mysql2sqlite.py dump.sql uno.sqlite

2. Copy `config.php.template` to `config.php` and set `$DB_FILE` (or set the
   `UNO_DB_FILE` environment variable).
3. Serve with Apache + PHP 8 (pdo_sqlite); use the rewrite rules from
   `htaccess_template` for the auto-versioned css/js files.

`data-input.php` has no authentication of its own; protect it in the web
server or in front of it.

## License

GPL-3.0-or-later, see `COPYING`.
