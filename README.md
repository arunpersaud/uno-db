# uno-db

Web interface for keeping UNO game statistics: players, sessions, games and
scores, with per-player statistics, comparisons, moving averages and charts.

Extracted (with history) from the `uno-db/` directory of
[UNO-darmstadt](https://sourceforge.net/p/uno-darmstadt/code/) (2009-2017).

## Status

- `main`: Python (Flask + Jinja2, package `unodb/`) on SQLite, with the old
  PHP code still in the repository.
- The PHP version needs schema version 4. The Flask app migrates the
  database to newer versions, so run the PHP code only on a copy made
  before that (see "Old PHP site" below).
- tag `mysql-final`: last MySQL version.

## Flask app

### Development

    uv sync
    uv run pytest
    FLASK_DATABASE=uno.sqlite uv run flask --app unodb run --debug

In debug mode the secret key and origin have defaults; passkeys work on
`http://localhost` (browsers treat localhost as secure).

### Configuration

Environment variables (Flask reads everything with the `FLASK_` prefix):

| Variable | Meaning |
|---|---|
| `FLASK_DATABASE` | the SQLite file |
| `FLASK_SECRET_KEY` | signs the login cookie; long and random, keep it secret |
| `FLASK_ORIGIN` | the site's address, e.g. `https://uno.example.org`; passkeys are bound to its host name |

`FLASK_SECRET_KEY` and `FLASK_ORIGIN` are required outside debug and test
mode. Changing the host name of `FLASK_ORIGIN` makes all passkeys invalid
(users then need new invite links).

### Database and migrations

Start from `schema-sqlite.sql` (empty) or `tools/mysql2sqlite.py` (MySQL
dump, see below). When the app starts it brings the schema up to date
(`unodb/migrations.py`). Before a migration it copies the database to
`backups/` next to it. `flask --app unodb uno migrate` does the same by
hand.

Public pages only read. Writes come from the admin pages and the command
line. Deleting sessions is a soft delete: they are hidden, not removed, and
can be restored. Every change is recorded in the table `audit_log`.

### Production

`Containerfile` builds the image (gunicorn on port 8000, database at
`/data/uno.sqlite`). Example with podman:

    podman build -t unodb .
    podman run -d --name unodb -v /srv/uno:/data \
        -e FLASK_ORIGIN=https://uno.example.org \
        -e FLASK_SECRET_KEY=... unodb

Put it behind a reverse proxy with HTTPS (passkeys need it).

## Users and logins

Logins use **passkeys** only (no passwords). There is no public sign-up:
an admin creates a user on the command line and sends them a one-time
link, with which they set up a passkey. Logged in users can add passkeys
for more devices on their start page (`/admin/`). (Entering and editing
games in the browser is being built; so far the admin area has the login
and the passkey management.)

Roles:

| Role | Can |
|---|---|
| `admin` | everything: any session, rename players, game types, locations, users |
| `editor` | edit and delete any session |
| `contributor` | enter sessions, edit and delete only their own |

Any number of users can have any role (e.g. two admins).

### Command line

All commands are `flask --app unodb uno <command>`. In the container, run
them with `podman exec` (the container has the database path and secrets
in its environment), e.g.

    podman exec unodb flask --app unodb uno users

| Command | Does |
|---|---|
| `invite NAME [--role ROLE] [--hours 48]` | creates the user if needed (default role: contributor) and prints a one-time link to set up a passkey. For an existing user it adds a passkey, e.g. after losing a phone |
| `users` | lists users with role, passkeys, sessions |
| `set-role NAME ROLE` | changes a role |
| `claim-sessions NAME` | gives NAME all sessions without an owner (data from before logins existed) |
| `game-types` | lists the game types with their owners |
| `assign-game-type SHORT NAME` | makes NAME the owner of a game type (they may edit its rules) |
| `remove-user NAME [--delete-sessions]` | removes the login (passkeys, open invites); with the flag also deletes all sessions NAME entered |
| `delete-sessions NAME` | deletes all sessions NAME entered |
| `restore-sessions NAME` | brings them back |
| `enable-user NAME` | allows a removed user to log in again (then send a new invite) |
| `migrate` | applies schema migrations |

### First admin

1. Create the user and the link (here with the container named `unodb`):

       podman exec unodb flask --app unodb uno invite "Your Name" --role admin

2. Open the printed link in the browser on your phone or computer, give
   the passkey a name and click "Set up passkey". You are logged in.
3. Make yourself the owner of the existing sessions:

       podman exec unodb flask --app unodb uno claim-sessions "Your Name"

4. Optional: on the start page, add a passkey for another device. Later
   logins: "Log in" in the footer.

### When someone misuses their login

    podman exec unodb flask --app unodb uno remove-user NAME --delete-sessions

This removes their passkeys and hides all their sessions from the
statistics. `restore-sessions NAME` undoes the second part.

## Old PHP site

1. Create the database, either empty

       sqlite3 uno.sqlite < schema-sqlite.sql

   or from a MySQL dump (made with `--skip-extended-insert`)

       tools/mysql2sqlite.py dump.sql uno.sqlite

2. Copy `config.php.template` to `config.php` and set `$DB_FILE` (or set the
   `UNO_DB_FILE` environment variable).
3. Serve with Apache + PHP 8 (pdo_sqlite); use the rewrite rules from
   `htaccess_template` for the auto-versioned css/js files.

The PHP code reads schema version 4 only. `data-input.php` has no
authentication of its own; block it in the web server.

## License

GPL-3.0-or-later, see `COPYING`.
