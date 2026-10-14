"""Public, read-only pages."""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from .db import WINNER, query, query_one

stats = Blueprint("stats", __name__)

SESSIONS_SQL = """
SELECT session.id, session.date, session.number_of_players,
       locations.name AS location, variations.name AS variation,
       variations.short AS variation_short,
       (SELECT count(*) FROM games WHERE games.session = session.id) AS games
FROM session
LEFT JOIN locations ON locations.id = session.location_id
LEFT JOIN variations ON variations.id = session.variation
"""
ORDER = " ORDER BY session.date DESC, session.id DESC"


@stats.app_template_filter()
def slug(name: str) -> str:
    """URL form of a player name: 'Raymond Wheeler' -> 'raymond-wheeler'."""
    return "-".join(name.lower().split())


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
    recent = query(SESSIONS_SQL + ORDER + " LIMIT 10")
    return render_template("index.html", totals=totals, recent=recent)


@stats.route("/sessions")
def sessions():
    return render_template("sessions.html", sessions=query(SESSIONS_SQL + ORDER))


@stats.route("/session/<date>")
def session(date):
    """All sessions of one day (sometimes there are several)."""
    infos = query(SESSIONS_SQL + " WHERE session.date = ? ORDER BY session.id", (date,))
    if not infos:
        abort(404)
    tables = [score_table(info["id"]) for info in infos]
    return render_template(
        "session.html",
        date=date,
        sessions=zip(infos, tables, strict=True),
        winner=WINNER,
    )


def score_table(session_id: int) -> dict:
    """Scores of one session: a column per player, a row per game."""
    rows = query(
        """SELECT games.id AS game, games.end_with_black_card AS black,
                  scores.player, players.name, scores.score
           FROM games
           JOIN scores ON scores.game = games.id
           JOIN players ON players.id = scores.player
           WHERE games.session = ?
           ORDER BY games.id, scores.position""",
        (session_id,),
    )

    # players in seating order of their first game
    players = {}
    games = {}
    for row in rows:
        players.setdefault(row["player"], row["name"])
        game = games.setdefault(row["game"], {"black": row["black"], "scores": {}})
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
    return {
        "players": players,
        "games": list(games.values()),
        "totals": totals,
        "wins": wins,
    }


@stats.route("/players")
def players():
    rows = query(
        """SELECT players.name, count(*) AS games,
                  sum(scores.score = :winner) AS wins,
                  max(session.date) AS last
           FROM players
           JOIN scores ON scores.player = players.id
           JOIN games ON games.id = scores.game
           JOIN session ON session.id = games.session
           GROUP BY players.id
           ORDER BY games DESC, players.name""",
        {"winner": WINNER},
    )
    return render_template("players.html", players=rows)


@stats.route("/player/<name>")
def player(name):
    by_slug = {slug(row["name"]): row for row in query("SELECT * FROM players")}
    row = by_slug.get(slug(name))
    if row is None:
        abort(404)
    if name != slug(row["name"]):
        return redirect(url_for(".player", name=slug(row["name"])), 301)

    sessions = query(
        """SELECT session.date, locations.name AS location,
                  count(*) AS games,
                  sum(scores.score = :winner) AS wins,
                  sum(iif(scores.score = :winner, 0, scores.score)) AS points
           FROM scores
           JOIN games ON games.id = scores.game
           JOIN session ON session.id = games.session
           LEFT JOIN locations ON locations.id = session.location_id
           WHERE scores.player = :player
           GROUP BY session.id
           ORDER BY session.date DESC, session.id DESC""",
        {"winner": WINNER, "player": row["id"]},
    )
    games = sum(s["games"] for s in sessions)
    wins = sum(s["wins"] for s in sessions)
    points = sum(s["points"] for s in sessions)
    summary = {
        "games": games,
        "wins": wins,
        "win_rate": wins / games if games else 0,
        "average": points / games if games else 0,
    }
    return render_template(
        "player.html", name=row["name"], summary=summary, sessions=sessions
    )
