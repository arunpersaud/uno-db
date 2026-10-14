"""Entering and editing sessions, games and game types (admin pages).

Permissions are checked here on every request, not only by hiding
buttons: contributors may change only the sessions (and game types) they
created; editors and admins may change all.

Players: admins and editors may pick any player. Contributors pick
players they created or who are in their own sessions; new players they
create need first and last name. A new name must not exist yet (compared
by its URL form, so "Joe Miller" and "joe-miller" are the same name).
"""

import re
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import abort, current_app, g, redirect, render_template, request, url_for

from .auth import admin, audit, login_required, now
from .db import WINNER, get_db, query, query_one
from .views import slug

MAX_SEATS = 12
MAX_SCORE = 1000
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@contextmanager
def transaction():
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except BaseException:
        db.execute("ROLLBACK")
        raise
    db.execute("COMMIT")


def today() -> str:
    zone = ZoneInfo(current_app.config.get("TIMEZONE", "America/Los_Angeles"))
    return datetime.now(zone).strftime("%Y-%m-%d")


def clean(text: str | None) -> str:
    """Trimmed, with single spaces."""
    return " ".join((text or "").split())


# --- permissions -------------------------------------------------------------


def edits_everything() -> bool:
    return g.user["role"] in ("admin", "editor")


def can_edit(session_row) -> bool:
    return edits_everything() or session_row["created_by"] == g.user["id"]


def editable_session(session_id: int):
    """The session row, if it exists, isn't deleted and may be edited."""
    row = query_one(
        "SELECT * FROM session WHERE id = ? AND deleted IS NULL", (session_id,)
    )
    if row is None:
        abort(404)
    if not can_edit(row):
        abort(403)
    return row


def pickable_players() -> list:
    """Players this user may put into a session."""
    if edits_everything():
        return query("SELECT id, name FROM players ORDER BY name")
    return query(
        """SELECT id, name FROM players WHERE created_by = :user
           OR id IN (SELECT player FROM session_players
                     JOIN session ON session.id = session_players.session
                     WHERE session.created_by = :user AND session.deleted IS NULL)
           ORDER BY name""",
        {"user": g.user["id"]},
    )


def new_name_problem(name: str) -> str | None:
    """Why NAME can't be a new player, or None."""
    if not 2 <= len(name) <= 60:
        return f"{name!r}: names need 2 to 60 characters."
    if g.user["role"] == "contributor" and len(name.split()) < 2:
        return f"{name!r}: please use first and last name (e.g. 'Joe Miller')."
    taken = {
        slug(row["name"]): row["name"] for row in query("SELECT name FROM players")
    }
    if slug(name) in taken:
        return (
            f"{name!r} is already taken (by {taken[slug(name)]!r})."
            " Please use a different name, e.g. with the last name."
        )
    return None


# --- sessions ----------------------------------------------------------------


@admin.route("/sessions")
@login_required
def sessions():
    where = "" if edits_everything() else " AND session.created_by = :user"
    rows = query(
        """SELECT session.id, session.date, locations.name AS location,
                  variations.short AS variation, users.name AS created_by,
                  (SELECT count(*) FROM games WHERE games.session = session.id)
                    AS games
           FROM session
           LEFT JOIN locations ON locations.id = session.location_id
           LEFT JOIN variations ON variations.id = session.variation
           LEFT JOIN users ON users.id = session.created_by
           WHERE session.deleted IS NULL"""
        + where
        + " ORDER BY session.date DESC, session.id DESC LIMIT 200",
        {"user": g.user["id"]},
    )
    return render_template("admin/sessions.html", sessions=rows)


def form_choices() -> dict:
    return {
        "locations": query("SELECT id, name FROM locations ORDER BY name"),
        "variants": query("SELECT id, name, short FROM variations ORDER BY id"),
        "pickable": pickable_players(),
        "max_seats": MAX_SEATS,
    }


def resolve_location(name: str, create: bool, problems: list, to_create: list):
    row = query_one("SELECT id FROM locations WHERE name = ? COLLATE NOCASE", (name,))
    if row is not None:
        return row["id"]
    if not name:
        problems.append("Please enter a location.")
    elif len(name) > 60:
        problems.append("The location name is too long.")
    elif not create:
        to_create.append(f"location {name!r}")
    return None


def resolve_player(name: str, create: bool, problems: list, to_create: list):
    """The id of a pickable player, or None (new, or a problem was added)."""
    pickable = {row["name"].lower(): row["id"] for row in pickable_players()}
    if name.lower() in pickable:
        return pickable[name.lower()]
    if query_one("SELECT 1 FROM players WHERE name = ? COLLATE NOCASE", (name,)):
        problems.append(
            f"{name!r} is a player of another group. Please use a different"
            " name for your player, e.g. with the last name."
        )
    elif problem := new_name_problem(name):
        problems.append(problem)
    elif not create:
        to_create.append(f"player {name!r}")
    return None


def resolve_players(names: list[str], create: bool, problems: list, to_create: list):
    """Player ids for names (None for new ones that may be created)."""
    if len(names) < 2:
        problems.append("A session needs at least two players.")
    if len({n.lower() for n in names}) < len(names):
        problems.append("A player is in the list twice.")
    return [resolve_player(name, create, problems, to_create) for name in names]


@admin.route("/sessions/new", methods=["GET", "POST"])
@login_required
def new_session():
    form = request.form
    default_variant = g.user["default_variant"] or 1
    if request.method == "GET":
        return render_template(
            "admin/session_new.html",
            values={"date": today(), "variant": default_variant, "players": []},
            **form_choices(),
        )

    values = {
        "date": form.get("date", ""),
        "location": clean(form.get("location")),
        "variant": form.get("variant", type=int),
        "players": [clean(n) for n in form.getlist("player") if clean(n)],
    }
    create = form.get("create") == "yes"
    problems, to_create = [], []
    if not DATE.fullmatch(values["date"]):
        problems.append("Please enter a date.")
    if query_one("SELECT 1 FROM variations WHERE id = ?", (values["variant"],)) is None:
        problems.append("Please pick a game type.")
    location_id = resolve_location(values["location"], create, problems, to_create)
    player_ids = resolve_players(values["players"], create, problems, to_create)
    if problems or to_create:
        return render_template(
            "admin/session_new.html",
            values=values,
            problems=problems,
            to_create=to_create if not problems else [],
            **form_choices(),
        )

    with transaction() as db:
        if location_id is None:
            location_id = db.execute(
                "INSERT INTO locations (name, created_by) VALUES (?, ?)",
                (values["location"], g.user["id"]),
            ).lastrowid
            audit("location created", g.user["id"], name=values["location"])
        for i, name in enumerate(values["players"]):
            if player_ids[i] is None:
                player_ids[i] = db.execute(
                    "INSERT INTO players (name, created_by) VALUES (?, ?)",
                    (name, g.user["id"]),
                ).lastrowid
                audit("player created", g.user["id"], name=name)
        session_id = db.execute(
            """INSERT INTO session (date, location_id, number_of_players, variation,
                                    created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (
                values["date"],
                location_id,
                len(player_ids),
                values["variant"],
                g.user["id"],
            ),
        ).lastrowid
        db.executemany(
            "INSERT INTO session_players (session, player, seat) VALUES (?, ?, ?)",
            [(session_id, pid, seat) for seat, pid in enumerate(player_ids)],
        )
        audit(
            "session created",
            g.user["id"],
            session=session_id,
            date=values["date"],
            location=values["location"],
            variant=values["variant"],
            players=values["players"],
        )
    return redirect(url_for("admin.edit_session", session_id=session_id), 303)


def session_players(session_id: int) -> list:
    return query(
        """SELECT players.id, players.name, session_players.seat
           FROM session_players JOIN players ON players.id = session_players.player
           WHERE session_players.session = ? ORDER BY session_players.seat""",
        (session_id,),
    )


def session_games(session_id: int) -> list[dict]:
    games = {}
    for row in query(
        """SELECT games.id, games.end_with_black_card AS black, scores.player,
                  scores.score
           FROM games LEFT JOIN scores ON scores.game = games.id
           WHERE games.session = ? ORDER BY games.id""",
        (session_id,),
    ):
        game = games.setdefault(
            row["id"], {"id": row["id"], "black": row["black"], "scores": {}}
        )
        if row["player"] is not None:
            game["scores"][row["player"]] = row["score"]
            if row["score"] == WINNER:
                game["winner"] = row["player"]
    return list(games.values())


def render_session(session_row, problems=(), values=None, edit=None):
    info = query_one(
        """SELECT locations.name AS location, variations.name AS variant
           FROM session LEFT JOIN locations ON locations.id = session.location_id
           LEFT JOIN variations ON variations.id = session.variation
           WHERE session.id = ?""",
        (session_row["id"],),
    )
    if edit is None:
        edit = request.args.get("edit", type=int)
    return render_template(
        "admin/session_edit.html",
        session=session_row,
        info=info,
        players=session_players(session_row["id"]),
        games=session_games(session_row["id"]),
        edit=edit,
        problems=problems,
        values=values or {},
        winner=WINNER,
        **form_choices(),
    )


@admin.route("/sessions/<int:session_id>")
@login_required
def edit_session(session_id):
    return render_session(editable_session(session_id))


def read_game_form(players) -> tuple[dict, list]:
    """Scores from the game form: {player id: score}, problems."""
    form = request.form
    problems = []
    winner = form.get("winner", type=int)
    scores = {}
    for p in players:
        if p["id"] == winner:
            scores[p["id"]] = WINNER
            continue
        text = form.get(f"score-{p['id']}", "").strip()
        if text == "":
            continue  # didn't play this game
        if not text.isdigit() or int(text) > MAX_SCORE:
            problems.append(f"{p['name']}: points must be a number from 0 to 1000.")
            continue
        scores[p["id"]] = int(text)
    if winner not in {p["id"] for p in players}:
        problems.append("Please mark who won.")
    elif len(scores) < 2:
        problems.append("A game needs at least two players with points.")
    return scores, problems


def game_values(scores: dict) -> dict:
    """Form values to show again after an error."""
    return {
        "winner": next((p for p, s in scores.items() if s == WINNER), None),
        "scores": {p: s for p, s in scores.items() if s != WINNER},
        "black": request.form.get("black") == "yes",
    }


@admin.post("/sessions/<int:session_id>/games")
@login_required
def add_game(session_id):
    session_row = editable_session(session_id)
    players = session_players(session_id)
    scores, problems = read_game_form(players)
    if problems:
        return render_session(session_row, problems, {"new": game_values(scores)})
    seats = {p["id"]: p["seat"] for p in players}
    black = request.form.get("black") == "yes"
    with transaction() as db:
        game_id = db.execute(
            "INSERT INTO games (session, end_with_black_card) VALUES (?, ?)",
            (session_id, int(black)),
        ).lastrowid
        db.executemany(
            "INSERT INTO scores (game, player, score, position) VALUES (?, ?, ?, ?)",
            [(game_id, p, s, seats[p]) for p, s in scores.items()],
        )
        audit(
            "game added",
            g.user["id"],
            session=session_id,
            game=game_id,
            scores=scores,
            black=black,
        )
    return redirect(url_for("admin.edit_session", session_id=session_id), 303)


def editable_game(session_id: int, game_id: int):
    session_row = editable_session(session_id)
    game = query_one(
        "SELECT * FROM games WHERE id = ? AND session = ?", (game_id, session_id)
    )
    if game is None:
        abort(404)
    return session_row, game


@admin.post("/sessions/<int:session_id>/games/<int:game_id>")
@login_required
def update_game(session_id, game_id):
    session_row, game = editable_game(session_id, game_id)
    players = session_players(session_id)
    scores, problems = read_game_form(players)
    if problems:
        return render_session(
            session_row, problems, {game_id: game_values(scores)}, edit=game_id
        )
    before = {
        r["player"]: r["score"]
        for r in query("SELECT player, score FROM scores WHERE game = ?", (game_id,))
    }
    seats = {p["id"]: p["seat"] for p in players}
    # keep the seat a player had in this game (old games: seats could differ)
    old_seats = {
        r["player"]: r["position"]
        for r in query("SELECT player, position FROM scores WHERE game = ?", (game_id,))
    }
    black = request.form.get("black") == "yes"
    with transaction() as db:
        db.execute("DELETE FROM scores WHERE game = ?", (game_id,))
        db.executemany(
            "INSERT INTO scores (game, player, score, position) VALUES (?, ?, ?, ?)",
            [(game_id, p, s, old_seats.get(p, seats[p])) for p, s in scores.items()],
        )
        db.execute(
            "UPDATE games SET end_with_black_card = ? WHERE id = ?",
            (int(black), game_id),
        )
        audit(
            "game changed",
            g.user["id"],
            session=session_id,
            game=game_id,
            before={"scores": before, "black": bool(game["end_with_black_card"])},
            after={"scores": scores, "black": black},
        )
    return redirect(url_for("admin.edit_session", session_id=session_id), 303)


@admin.post("/sessions/<int:session_id>/games/<int:game_id>/delete")
@login_required
def delete_game(session_id, game_id):
    _, game = editable_game(session_id, game_id)
    before = {
        r["player"]: r["score"]
        for r in query("SELECT player, score FROM scores WHERE game = ?", (game_id,))
    }
    with transaction() as db:
        db.execute("DELETE FROM scores WHERE game = ?", (game_id,))
        db.execute("DELETE FROM games WHERE id = ?", (game_id,))
        audit(
            "game deleted",
            g.user["id"],
            session=session_id,
            game=game_id,
            scores=before,
            black=bool(game["end_with_black_card"]),
        )
    return redirect(url_for("admin.edit_session", session_id=session_id), 303)


@admin.post("/sessions/<int:session_id>/details")
@login_required
def update_session(session_id):
    session_row = editable_session(session_id)
    form = request.form
    date = form.get("date", "")
    location = clean(form.get("location"))
    variant = form.get("variant", type=int)
    create = form.get("create") == "yes"
    problems, to_create = [], []
    if not DATE.fullmatch(date):
        problems.append("Please enter a date.")
    if query_one("SELECT 1 FROM variations WHERE id = ?", (variant,)) is None:
        problems.append("Please pick a game type.")
    location_id = resolve_location(location, create, problems, to_create)
    if to_create and not problems:
        problems.append(
            f"There is no location {location!r} yet; tick 'create' to add it."
        )
    if problems:
        return render_session(session_row, problems)
    with transaction() as db:
        if location_id is None:
            location_id = db.execute(
                "INSERT INTO locations (name, created_by) VALUES (?, ?)",
                (location, g.user["id"]),
            ).lastrowid
            audit("location created", g.user["id"], name=location)
        db.execute(
            "UPDATE session SET date = ?, location_id = ?, variation = ? WHERE id = ?",
            (date, location_id, variant, session_id),
        )
        audit(
            "session changed",
            g.user["id"],
            session=session_id,
            before={
                "date": session_row["date"],
                "location": session_row["location_id"],
                "variant": session_row["variation"],
            },
            after={"date": date, "location": location_id, "variant": variant},
        )
    return redirect(url_for("admin.edit_session", session_id=session_id), 303)


@admin.post("/sessions/<int:session_id>/players")
@login_required
def add_player(session_id):
    """Someone joins the session later: a new seat at the end."""
    session_row = editable_session(session_id)
    name = clean(request.form.get("player"))
    create = request.form.get("create") == "yes"
    players = session_players(session_id)
    if name.lower() in {p["name"].lower() for p in players}:
        return render_session(session_row, [f"{name} is already in this session."])
    if len(players) >= MAX_SEATS:
        return render_session(session_row, [f"At most {MAX_SEATS} players."])
    problems, to_create = [], []
    player_id = resolve_player(name, create, problems, to_create)
    if to_create and not problems:
        problems.append(f"There is no player {name!r} yet; tick 'create' to add it.")
    if problems:
        return render_session(session_row, problems)
    with transaction() as db:
        if player_id is None:
            player_id = db.execute(
                "INSERT INTO players (name, created_by) VALUES (?, ?)",
                (name, g.user["id"]),
            ).lastrowid
            audit("player created", g.user["id"], name=name)
        db.execute(
            "INSERT INTO session_players (session, player, seat) VALUES (?, ?, ?)",
            (session_id, player_id, max((p["seat"] for p in players), default=-1) + 1),
        )
        db.execute(
            "UPDATE session SET number_of_players = number_of_players + 1 WHERE id = ?",
            (session_id,),
        )
        audit("player joined", g.user["id"], session=session_id, player=name)
    return redirect(url_for("admin.edit_session", session_id=session_id), 303)


@admin.post("/sessions/<int:session_id>/delete")
@login_required
def delete_session(session_id):
    editable_session(session_id)
    get_db().execute("UPDATE session SET deleted = ? WHERE id = ?", (now(), session_id))
    audit("session deleted", g.user["id"], session=session_id)
    return redirect(url_for("admin.sessions"), 303)


# --- game types --------------------------------------------------------------


def editable_variant(variant_id: int):
    row = query_one("SELECT * FROM variations WHERE id = ?", (variant_id,))
    if row is None:
        abort(404)
    if not (g.user["role"] == "admin" or row["created_by"] == g.user["id"]):
        abort(403)
    return row


@admin.route("/variants/new", methods=["GET", "POST"])
@admin.route("/variants/<int:variant_id>", methods=["GET", "POST"])
@login_required
def variant_form(variant_id=None):
    row = editable_variant(variant_id) if variant_id else None
    values = dict(row) if row else {"name": "", "short": "", "description": ""}
    problems = []
    if request.method == "POST":
        values = {
            "name": clean(request.form.get("name")),
            "short": clean(request.form.get("short")),
            "description": (request.form.get("description") or "").strip(),
        }
        if not 2 <= len(values["name"]) <= 60:
            problems.append("The name needs 2 to 60 characters.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,19}", values["short"]):
            problems.append(
                "The short name needs 1 to 20 letters, digits or '-' (it's used"
                " in the address of the rules page)."
            )
        if len(values["description"]) < 20:
            problems.append("Please describe the rules (at least a sentence).")
        clash = query_one(
            "SELECT id FROM variations WHERE short = ? AND id IS NOT ?",
            (values["short"], variant_id),
        )
        if clash:
            problems.append(f"The short name {values['short']!r} is already used.")
        if not problems:
            with transaction() as db:
                if row is None:
                    variant_id = db.execute(
                        """INSERT INTO variations (name, short, description, created_by)
                           VALUES (?, ?, ?, ?)""",
                        (
                            values["name"],
                            values["short"],
                            values["description"],
                            g.user["id"],
                        ),
                    ).lastrowid
                    audit(
                        "game type created", g.user["id"], variant=variant_id, **values
                    )
                else:
                    db.execute(
                        """UPDATE variations SET name = ?, short = ?, description = ?
                           WHERE id = ?""",
                        (
                            values["name"],
                            values["short"],
                            values["description"],
                            variant_id,
                        ),
                    )
                    audit(
                        "game type changed",
                        g.user["id"],
                        variant=variant_id,
                        before={k: row[k] for k in values},
                        after=values,
                    )
            next_url = request.form.get("next") or ""
            if next_url.startswith("/admin/"):
                return redirect(next_url, 303)
            return redirect(url_for("stats.variant", short=values["short"]), 303)
    return render_template(
        "admin/variant_form.html",
        variant=row,
        values=values,
        problems=problems,
        next=request.values.get("next", ""),
    )


@admin.post("/settings")
@login_required
def settings():
    variant = request.form.get("default_variant", type=int)
    if query_one("SELECT 1 FROM variations WHERE id = ?", (variant,)) is None:
        abort(400)
    get_db().execute(
        "UPDATE users SET default_variant = ? WHERE id = ?", (variant, g.user["id"])
    )
    audit("default game type", g.user["id"], variant=variant)
    return redirect(url_for("admin.start"), 303)
