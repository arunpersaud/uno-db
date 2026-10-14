"""Public, read-only pages."""

from flask import (
    Blueprint,
    abort,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from . import stats as st
from .db import WINNER, query, query_one

stats = Blueprint("stats", __name__)

SESSION_COLUMNS = {
    "date": True,
    "location": False,
    "number_of_players": True,
    "games": True,
    "average": True,
}
MAX_COMPARE = 6  # chart colors that stay apart, also for color blindness

PLAYER_COLUMNS = {
    "name": False,
    "games": True,
    "wins": True,
    "win_rate": True,
    "average": True,
    "last": True,
}


@stats.app_template_filter()
def slug(name: str) -> str:
    """URL form of a player name: 'Raymond Wheeler' -> 'raymond-wheeler'."""
    return "-".join(name.lower().split())


@stats.app_template_filter()
def percent(value: float) -> str:
    return f"{100 * value:.1f}%"


@stats.app_template_filter()
def number(value: float) -> str:
    return f"{value:.1f}"


def newest_first(session_list: list[dict]) -> list[dict]:
    return sorted(session_list, key=lambda s: (s["date"], s["id"]), reverse=True)


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
    rows = st.all_scores()
    session_list = st.sessions(rows)

    # active players: everyone who played in the last year with games
    since = query_one("SELECT date(max(date), '-1 year') AS since FROM session")
    since = since["since"]
    active = st.players([row for row in rows if row["date"] >= since])
    active.sort(key=lambda p: (-p["games"], p["name"]))

    return render_template(
        "index.html",
        totals=totals,
        recent=newest_first(session_list)[:10],
        active=active[:10],
        since=since,
        overview=st.overview(rows),
        records=st.records(session_list, st.games(rows)),
    )


@stats.route("/contribute")
def contribute():
    return render_template("contribute.html")


@stats.route("/sessions")
def sessions():
    rows = st.all_scores()
    session_list = newest_first(st.sessions(rows))
    sort = st.Sort(SESSION_COLUMNS, "date")
    return render_template(
        "sessions.html",
        sessions=sort.apply(session_list),
        sort=sort,
        records=st.records(session_list, st.games(rows)),
    )


@stats.route("/session/<date>")
def session(date):
    """All sessions of one day (sometimes there are several)."""
    rows = st.all_scores(" WHERE session.date = ?", (date,))
    if not rows:
        abort(404)
    session_list = st.sessions(rows)
    tables = [score_table(s["id"]) for s in session_list]
    return render_template(
        "session.html",
        date=date,
        sessions=zip(session_list, tables, strict=True),
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
    return {
        "players": players,
        "games": list(games.values()),
        "totals": totals,
        "wins": wins,
    }


@stats.route("/players")
def players():
    # default: most recently played, then most wins
    player_list = sorted(
        st.players(st.all_scores()), key=lambda p: (-p["wins"], p["name"])
    )
    sort = st.Sort(PLAYER_COLUMNS, "last")
    return render_template("players.html", players=sort.apply(player_list), sort=sort)


def find_player(name: str):
    """(players row, None), or (None, redirect to the canonical URL)."""
    by_slug = players_by_slug()
    row = by_slug.get(slug(name))
    if row is None:
        abort(404)
    if name != slug(row["name"]):
        args = request.view_args | {"name": slug(row["name"])}
        return None, redirect(url_for(request.endpoint, **args), 301)
    return row, None


@stats.route("/player/<name>")
def player(name):
    row, response = find_player(name)
    if response:
        return response
    data = st.player(st.all_scores(" WHERE scores.player = ?", (row["id"],)))
    sort = st.Sort(SESSION_COLUMNS | {"wins": True}, "date")
    by_date = request.args.get("x") == "date"
    return render_template(
        "player.html",
        name=row["name"],
        by_date=by_date,
        all_players=all_players_by_games(),
        summary=data["summary"],
        group_sizes=data["group_sizes"],
        sessions=sort.apply(newest_first(data["sessions"])),
        sort=sort,
    )


@stats.route("/player/<name>/charts.json")
def player_charts(name):
    row, response = find_player(name)
    if response:
        return response
    rows = st.all_scores(" WHERE scores.player = ?", (row["id"],))
    return jsonify(st.player_charts(rows, by_date=request.args.get("x") == "date"))


def chart_options() -> dict:
    """Chart options from the URL, as query arguments for links."""
    keep = {}
    if request.args.get("games") == "together":
        keep["games"] = "together"
    if request.args.get("x") == "date":
        keep["x"] = "date"
    return keep


def all_players_by_games() -> list[dict]:
    """All players, most games first (for the player pickers)."""
    players = st.players(st.all_scores())
    players.sort(key=lambda p: (-p["games"], p["name"]))
    return players


def players_by_slug() -> dict:
    return {slug(row["name"]): row for row in query("SELECT * FROM players")}


def compare_url(slugs: list[str], **args) -> str:
    if not slugs:
        return url_for(".compare", **args)
    return url_for(".compare", names="/".join(slugs), **args)


@stats.route("/compare/")
@stats.route("/compare/<path:names>")
def compare(names=""):
    known = players_by_slug()
    requested = [n for n in names.split("/") if n]
    selected = []
    for name in requested:
        if slug(name) not in known:
            abort(404)
        if slug(name) not in selected:
            selected.append(slug(name))
    keep = chart_options()

    error = None
    if added := request.args.get("add", "").strip():
        if slug(added) not in known:
            error = f"There is no player called {added}."
        elif slug(added) in selected:
            error = f"{known[slug(added)]['name']} is already in the comparison."
        elif len(selected) >= MAX_COMPARE:
            error = f"At most {MAX_COMPARE} players can be compared."
        else:
            return redirect(compare_url(selected + [slug(added)], **keep))
    elif selected[:MAX_COMPARE] != requested:
        return redirect(compare_url(selected[:MAX_COMPARE], **keep), 301)

    players = [known[s] for s in selected]
    data = None
    if len(players) >= 2:
        data = st.compare(
            [
                (p["name"], st.all_scores(" WHERE scores.player = ?", (p["id"],)))
                for p in players
            ]
        )
    # status 200 even with an error message: htmx doesn't swap in 4xx pages
    response = make_response(
        render_template(
            "compare.html",
            players=players,
            selected=selected,
            data=data,
            keep=keep,
            error=error,
            all_players=all_players_by_games(),
            max_players=MAX_COMPARE,
            compare_url=compare_url,
        )
    )
    # htmx shows this in the address bar (not the ?add=... request)
    response.headers["HX-Push-Url"] = compare_url(selected, **keep)
    return response


@stats.route("/compare.json/<path:names>")
def compare_charts(names):
    known = players_by_slug()
    selected = [slug(n) for n in names.split("/") if n]
    if not 2 <= len(selected) <= MAX_COMPARE or any(s not in known for s in selected):
        abort(404)
    players = [
        (known[s]["name"], st.all_scores(" WHERE scores.player = ?", (known[s]["id"],)))
        for s in selected
    ]
    together = request.args.get("games") == "together"
    by_date = request.args.get("x") == "date"
    return jsonify(st.compare_charts(players, together, by_date))
