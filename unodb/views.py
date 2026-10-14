"""Public, read-only pages."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from . import export, markdown, ratings
from . import stats as st
from .db import WINNER, query, query_one, read_only

stats = Blueprint("stats", __name__)
# public pages never write
stats.before_request(read_only)

# pages without the game type filter
UNFILTERED = {
    "stats.contribute",
    "stats.variants",
    "stats.variant",
    "stats.root_file",
    "stats.favicon",
    "stats.security_txt",
}


@stats.before_request
def variant_filter():
    """g.variants: the game types picked with ?variant=<short> (empty: all)."""
    g.all_variants = query("SELECT id, name, short FROM variations ORDER BY id")
    by_short = {v["short"].lower(): v for v in g.all_variants}
    picked = {
        by_short[w.lower()]["id"]
        for w in request.args.getlist("variant")
        if w.lower() in by_short
    }
    g.variants = [v for v in g.all_variants if v["id"] in picked]
    if len(g.variants) == len(g.all_variants):
        g.variants = []
    g.show_filter = len(g.all_variants) > 1 and request.endpoint not in UNFILTERED


@stats.url_defaults
def keep_filter(endpoint, values):
    """Links between the stats pages keep the game type filter."""
    if g.get("variants") and "variant" not in values and endpoint not in UNFILTERED:
        values["variant"] = [v["short"] for v in g.variants]


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
    "win_ratio": True,
    "average": True,
    "last": True,
}


@stats.app_template_filter()
def slug(name: str) -> str:
    """URL form of a player name: 'Raymond Wheeler' -> 'raymond-wheeler'."""
    return "-".join(name.lower().split())


@stats.app_template_filter("markdown")
def markdown_filter(text: str | None):
    return markdown.render(text)


@stats.app_template_filter()
def percent(value: float) -> str:
    return f"{100 * value:.1f}%"


@stats.app_template_filter()
def number(value: float) -> str:
    return f"{value:.1f}"


@stats.app_template_filter()
def ratio(value: float) -> str:
    """Wins compared to chance: 1.23×."""
    return f"{value:.2f}×"


def newest_first(session_list: list[dict]) -> list[dict]:
    return sorted(session_list, key=lambda s: (s["date"], s["id"]), reverse=True)


@stats.route("/")
def index():
    rows = st.all_scores()
    session_list = st.sessions(rows)
    dates = sorted({row["date"] for row in rows})
    known = [d for d in dates if st.timestamp(d, 0) is not None]
    totals = {
        "players": len({row["player"] for row in rows}),
        "first": known[0] if known else None,
        "last": dates[-1] if dates else None,
    }

    # active players: everyone who played in the last year with games
    since = f"{int(known[-1][:4]) - 1}{known[-1][4:]}" if known else ""
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


# --- files at the root of the site ----------------------------------------------

ROOT_FILES = Path(__file__).parent / "root"


@stats.route("/<any(robots.txt, humans.txt, llms.txt):name>")
def root_file(name):
    return send_from_directory(ROOT_FILES, name, mimetype="text/plain", max_age=86400)


@stats.route("/favicon.ico")
def favicon():
    return send_from_directory(
        Path(__file__).parent / "static",
        "draw4.png",
        mimetype="image/png",
        max_age=86400,
    )


@stats.route("/.well-known/security.txt")
def security_txt():
    """RFC 9116; Expires must be at most a year ahead, so it's computed."""
    expires = datetime.now(UTC) + timedelta(days=365)
    text = (
        "Contact: mailto:arun@nubati.net\n"
        f"Expires: {expires:%Y-%m-%dT00:00:00Z}\n"
        "Preferred-Languages: en, de\n"
        f"Canonical: {current_app.config['ORIGIN']}/.well-known/security.txt\n"
    )
    return current_app.response_class(text, mimetype="text/plain")


@stats.route("/variants")
def variants():
    rows = query(
        """SELECT variations.*, count(session.id) AS sessions
           FROM variations LEFT JOIN session ON session.variation = variations.id
             AND session.deleted IS NULL
           GROUP BY variations.id ORDER BY sessions DESC, variations.name"""
    )
    return render_template("variants.html", variants=rows)


@stats.route("/variant/<short>")
def variant(short):
    row = query_one(
        """SELECT variations.*, users.name AS author FROM variations
           LEFT JOIN users ON users.id = variations.created_by WHERE short = ?""",
        (short,),
    )
    if row is None:
        abort(404)
    games = query_one(
        """SELECT count(DISTINCT session.id) AS sessions, count(games.id) AS games
           FROM session LEFT JOIN games ON games.session = session.id
           WHERE session.variation = ? AND session.deleted IS NULL""",
        (row["id"],),
    )
    return render_template("variant.html", variant=row, counts=games)


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
    rows = st.all_scores(" AND session.date = ?", (date,))
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
    rows = st.all_scores(" AND scores.player = ?", (row["id"],))
    if not rows and not g.variants:
        # no games (left): e.g. all their sessions were deleted
        abort(404)
    data = st.player(rows)
    sort = st.Sort(SESSION_COLUMNS | {"wins": True}, "date")
    rated = ratings.table(ratings.cached(st.all_scores(), "winner"), RATING_MIN_GAMES)
    rating = next(
        ({"rank": i + 1, "of": len(rated), **r} for i, r in enumerate(rated)
         if r["player"] == row["id"]),
        None,
    )  # fmt: skip
    by_date = request.args.get("x") == "date"
    return render_template(
        "player.html",
        name=row["name"],
        rating=rating,
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
    rows = st.all_scores(" AND scores.player = ?", (row["id"],))
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
        player_rows = [
            (p["name"], st.all_scores(" AND scores.player = ?", (p["id"],)))
            for p in players
        ]
        data = st.compare(player_rows)
        data["correlation"] = st.correlations(player_rows)

    everyone = all_players_by_games()
    # status 200 even with an error message: htmx doesn't swap in 4xx pages
    response = make_response(
        render_template(
            "compare.html",
            players=players,
            selected=selected,
            data=data,
            keep=keep,
            error=error,
            all_players=everyone,
            # always the same number of suggestions, without the picked ones
            suggestions=[p for p in everyone if slug(p["name"]) not in selected][:10],
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
        (known[s]["name"], st.all_scores(" AND scores.player = ?", (known[s]["id"],)))
        for s in selected
    ]
    together = request.args.get("games") == "together"
    by_date = request.args.get("x") == "date"
    return jsonify(st.compare_charts(players, together, by_date))


# --- ratings ---------------------------------------------------------------------

RATING_MIN_GAMES = 30
# sort key -> sorts descending by default; points vs. the table: fewer first
RATING_COLUMNS = {
    "rating": True,
    "name": False,
    "games": True,
    "win_ratio": True,
    "vs_table_average": False,
}
RATING_CHART_PLAYERS = 6


def rating_mode() -> str:
    return "points" if request.args.get("losers") == "points" else "winner"


@stats.route("/ratings")
def ratings_page():
    rows = st.all_scores()
    mode = rating_mode()
    result = ratings.cached(rows, mode)
    ratio = {p["name"]: p["win_ratio"] for p in st.players(rows)}
    vs_table = ratings.points_vs_table(rows)
    table = ratings.table(result, RATING_MIN_GAMES)
    for rank, row in enumerate(table, 1):
        row["rank"] = rank
        row["win_ratio"] = ratio.get(row["name"], 0.0)
        row.update(
            {f"vs_table_{k}": v for k, v in vs_table.get(row["player"], {}).items()}
        )
        row.setdefault("vs_table_average", None)
        row.setdefault("vs_table_ci", None)
    sort = st.Sort(RATING_COLUMNS, "rating")
    table = sort.apply(table)
    evaluation = {m: ratings.evaluate(ratings.cached(rows, m)) for m in ratings.MODES}
    return render_template(
        "ratings.html",
        table=table,
        sort=sort,
        mode=mode,
        evaluation=evaluation,
        min_games=RATING_MIN_GAMES,
        chart_players=RATING_CHART_PLAYERS,
        beta=ratings.BETA,
        keep={"losers": "points"} if mode == "points" else {},
    )


@stats.route("/ratings.json")
def ratings_chart():
    """Rating over time of the best rated players (date axis, as the
    compare page)."""
    rows = st.all_scores()
    result = ratings.cached(rows, rating_mode())
    top = ratings.table(result, RATING_MIN_GAMES)[:RATING_CHART_PLAYERS]
    nr = st.day_numbers(rows)
    values = []
    for player in top:
        values.append(
            {
                t: round(rating, 2)
                for date, game, rating in result.history[player["player"]]
                if (t := st.timestamp(date, nr[game])) is not None
            }
        )
    return jsonify(
        names=[p["name"] for p in top], by_date=True, **st.with_breaks(values)
    )


# --- CSV downloads -------------------------------------------------------------


@stats.route("/session/<date>.csv")
def session_csv(date):
    rows = st.all_scores(" AND session.date = ?", (date,))
    if not rows:
        abort(404)
    return export.csv_response(
        f"uno-{date}.csv", export.SCORE_HEADER, export.score_rows(rows)
    )


@stats.route("/scores.csv")
def scores_csv():
    """All scores (of the picked game types)."""
    return export.csv_response(
        "uno-scores.csv", export.SCORE_HEADER, export.score_rows(st.all_scores())
    )


SESSION_HEADER = [
    "date",
    "location",
    "game_type",
    "players",
    "games",
    "points_per_game",
]


@stats.route("/sessions.csv")
def sessions_csv():
    rows = newest_first(st.sessions(st.all_scores()))
    return export.csv_response(
        "uno-sessions.csv",
        SESSION_HEADER,
        (
            [s["date"], s["location"], s["variation"], s["number_of_players"],
             s["games"], round(s["average"], 2)]
            for s in rows
        ),
    )  # fmt: skip


@stats.route("/player/<name>/sessions.csv")
def player_sessions_csv(name):
    row, response = find_player(name)
    if response:
        return response
    data = st.player(st.all_scores(" AND scores.player = ?", (row["id"],)))
    return export.csv_response(
        f"uno-{slug(row['name'])}-sessions.csv",
        ["date", "location", "game_type", "players", "games", "wins", "points",
         "points_per_game"],
        (
            [s["date"], s["location"], s["variation"], s["number_of_players"],
             s["games"], s["wins"], s["points"], round(s["average"], 2)]
            for s in newest_first(data["sessions"])
        ),
    )  # fmt: skip
