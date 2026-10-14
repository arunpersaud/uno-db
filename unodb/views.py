"""Public, read-only pages."""

from flask import Blueprint, abort, redirect, render_template, request

from .db import WINNER, query, query_one

stats = Blueprint("stats", __name__)

SESSIONS_SQL = """
SELECT session.id, session.date, session.number_of_players,
       locations.name AS location, variations.short AS variation,
       (SELECT count(*) FROM games WHERE games.session = session.id) AS games
FROM session
LEFT JOIN locations ON locations.id = session.location_id
LEFT JOIN variations ON variations.id = session.variation
ORDER BY session.date DESC, session.id DESC
"""


@stats.route("/")
def index():
    # old links like /?name=Arun: the PHP site still has those pages
    if request.query_string:
        return redirect("/index.php?" + request.query_string.decode())
    totals = query_one(
        """SELECT (SELECT count(*) FROM games) AS games,
                  (SELECT count(*) FROM session) AS sessions,
                  (SELECT count(DISTINCT player) FROM scores) AS players,
                  (SELECT min(date) FROM session
                   WHERE date GLOB '[12][0-9][0-9][0-9]-*') AS first,
                  (SELECT max(date) FROM session) AS last"""
    )
    recent = query(SESSIONS_SQL + " LIMIT 10")
    return render_template("index.html", totals=totals, recent=recent)


@stats.route("/sessions")
def sessions():
    return render_template("sessions.html", sessions=query(SESSIONS_SQL))


@stats.route("/sessions/<int:session_id>")
def session(session_id):
    info = query_one(
        """SELECT session.id, session.date, session.number_of_players,
                  locations.name AS location, variations.name AS variation
           FROM session
           LEFT JOIN locations ON locations.id = session.location_id
           LEFT JOIN variations ON variations.id = session.variation
           WHERE session.id = ?""",
        (session_id,),
    )
    if info is None:
        abort(404)

    rows = query(
        """SELECT games.id AS game, games.end_with_black_card AS black,
                  scores.player, players.name, scores.score, scores.position
           FROM games
           JOIN scores ON scores.game = games.id
           JOIN players ON players.id = scores.player
           WHERE games.session = ?
           ORDER BY games.id, scores.position""",
        (session_id,),
    )

    # one column per player, in seating order of their first game
    players = {}
    games = {}
    for row in rows:
        players.setdefault(row["player"], row["name"])
        game = games.setdefault(
            row["game"], {"id": row["game"], "black": row["black"], "scores": {}}
        )
        game["scores"][row["player"]] = row["score"]

    totals = {
        player: sum(
            game["scores"].get(player, 0)
            for game in games.values()
            if game["scores"].get(player) != WINNER
        )
        for player in players
    }
    wins = {
        player: sum(game["scores"].get(player) == WINNER for game in games.values())
        for player in players
    }
    return render_template(
        "session.html",
        info=info,
        players=players,
        games=list(games.values()),
        totals=totals,
        wins=wins,
        winner=WINNER,
    )
