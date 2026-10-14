"""Statistics, computed in Python from plain rows.

The data is small (about 7500 scores), so each page fetches the rows it
needs once and aggregates them here. Points: a win counts as 0 (the winner
has the score WINNER in the database), as in the old PHP site.
"""

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from statistics import StatisticsError, correlation, fmean, pstdev

from flask import request, url_for

from .db import WINNER, query

MOVING_WINDOW = 20
HISTOGRAM_BIN = 10
HISTOGRAM_MAX = 150  # last bin: this and more

SCORES_SQL = """
SELECT session.id AS session, session.date, session.number_of_players,
       locations.name AS location, variations.name AS variation,
       games.id AS game, games.end_with_black_card AS black,
       scores.player, players.name, scores.score, scores.position
FROM scores
JOIN games ON games.id = scores.game
JOIN session ON session.id = games.session
JOIN players ON players.id = scores.player
LEFT JOIN locations ON locations.id = session.location_id
LEFT JOIN variations ON variations.id = session.variation
"""
CHRONOLOGICAL = " ORDER BY session.date, session.id, games.id, scores.position"


def points(score: int) -> int:
    return 0 if score == WINNER else score


def summarize(scores: list[int]) -> dict:
    """Games, wins, points, average and sigma of a list of raw scores."""
    pts = [points(s) for s in scores]
    games = len(pts)
    wins = sum(s == WINNER for s in scores)
    return {
        "games": games,
        "wins": wins,
        "win_rate": wins / games if games else 0.0,
        "points": sum(pts),
        "average": fmean(pts) if pts else 0.0,
        "sigma": pstdev(pts) if pts else 0.0,
    }


def all_scores(where: str = "", params: tuple | dict = ()) -> list:
    return query(SCORES_SQL + where + CHRONOLOGICAL, params)


def sessions(rows) -> list[dict]:
    """One entry per session, with the stats of its scores."""
    by_session = {}
    for row in rows:
        entry = by_session.setdefault(
            row["session"],
            {
                "id": row["session"],
                "date": row["date"],
                "location": row["location"],
                "variation": row["variation"],
                "number_of_players": row["number_of_players"],
                "game_ids": set(),
                "scores": [],
            },
        )
        entry["game_ids"].add(row["game"])
        entry["scores"].append(row["score"])
    result = []
    for entry in by_session.values():
        stats = summarize(entry.pop("scores"))
        # summarize() counts scores; a session's games are games, not scores
        stats["scores"] = stats.pop("games")
        entry.update(stats, games=len(entry.pop("game_ids")))
        result.append(entry)
    return result


def games(rows) -> list[dict]:
    """One entry per game: average points of everyone at the table."""
    by_game = {}
    for row in rows:
        entry = by_game.setdefault(
            row["game"],
            {
                "id": row["game"],
                "date": row["date"],
                "location": row["location"],
                "scores": [],
            },
        )
        entry["scores"].append(row["score"])
    for entry in by_game.values():
        entry["players"] = len(entry["scores"])
        entry["average"] = fmean(points(s) for s in entry.pop("scores"))
    return list(by_game.values())


def records(session_list: list[dict], game_list: list[dict]) -> dict:
    """Highest and lowest scoring sessions and games."""

    def by_average(entry):
        return entry["average"]

    return {
        "high_session": max(session_list, key=by_average, default=None),
        "low_session": min(session_list, key=by_average, default=None),
        "high_game": max(game_list, key=by_average, default=None),
        "low_game": min(game_list, key=by_average, default=None),
    }


def overview(rows) -> dict:
    """The summary paragraph of the old site's home page."""
    pts = [points(row["score"]) for row in rows]
    black = [points(row["score"]) for row in rows if row["black"]]
    game_list = {row["game"]: row["black"] for row in rows}
    sizes = {row["session"]: row["number_of_players"] for row in rows}
    return {
        "sessions": len(sizes),
        "games": len(game_list),
        "scores": len(pts),
        "average": fmean(pts) if pts else 0.0,
        "black_rate": sum(game_list.values()) / len(game_list) if game_list else 0.0,
        "black_average": fmean(black) if black else 0.0,
        "min_size": min(sizes.values(), default=0),
        "max_size": max(sizes.values(), default=0),
        "average_size": fmean(sizes.values()) if sizes else 0.0,
    }


def players(rows) -> list[dict]:
    by_player = defaultdict(list)
    names = {}
    last = {}
    for row in rows:
        by_player[row["player"]].append(row["score"])
        names[row["player"]] = row["name"]
        last[row["player"]] = row["date"]
    return [
        {"name": names[p], "last": last[p], **summarize(scores)}
        for p, scores in by_player.items()
    ]


def player(rows) -> dict:
    """Everything on a player page; rows: this player's scores, in order."""
    scores = [row["score"] for row in rows]
    summary = summarize(scores)
    summary["sessions"] = len({row["session"] for row in rows})
    # unknown dates like 1???-??-?? sort first: skip them
    dated = [row["date"] for row in rows if timestamp(row["date"], 0) is not None]
    summary["first"] = dated[0] if dated else None
    summary["last"] = rows[-1]["date"] if rows else None
    summary["highest"] = max((points(s) for s in scores), default=0)
    summary["black"] = sum(row["black"] for row in rows)

    # longest run of wins in a row
    streak = best = 0
    for score in scores:
        streak = streak + 1 if score == WINNER else 0
        best = max(best, streak)
    summary["streak"] = best

    by_size = defaultdict(list)
    for row in rows:
        by_size[row["number_of_players"]].append(row["score"])
    group_sizes = [
        {"size": size, **summarize(s)} for size, s in sorted(by_size.items())
    ]

    session_list = sessions(rows)
    summary["best_session"] = min(
        session_list, key=lambda s: s["average"], default=None
    )
    summary["worst_session"] = max(
        session_list, key=lambda s: s["average"], default=None
    )

    return {"summary": summary, "group_sizes": group_sizes, "sessions": session_list}


def moving_average(rows) -> list[float | None]:
    """Average points of the last MOVING_WINDOW games, None before that."""
    pts = [points(row["score"]) for row in rows]
    return [
        round(fmean(pts[i + 1 - MOVING_WINDOW : i + 1]), 2)
        if i + 1 >= MOVING_WINDOW
        else None
        for i in range(len(pts))
    ]


def histogram(rows) -> dict:
    """Games per points bin: wins, then bins of HISTOGRAM_BIN points."""
    labels = ["won"] + [
        f"{lo}–{lo + HISTOGRAM_BIN - 1}"
        for lo in range(0, HISTOGRAM_MAX, HISTOGRAM_BIN)
    ]
    labels.append(f"{HISTOGRAM_MAX}+")
    counts = [0] * len(labels)
    for row in rows:
        if row["score"] == WINNER:
            counts[0] += 1
        else:
            counts[1 + min(row["score"], HISTOGRAM_MAX) // HISTOGRAM_BIN] += 1
    return {"labels": labels, "counts": counts}


def day_numbers(rows) -> dict[int, int]:
    """game id -> number of the game on its day (0, 1, ...).

    Per day, not per session: some days have several sessions.
    """
    days = defaultdict(set)
    for row in rows:
        days[row["date"]].add((row["session"], row["game"]))
    return {
        game: i for games in days.values() for i, (_, game) in enumerate(sorted(games))
    }


# a longer pause in a player's games breaks the line in the date charts
BREAK_AFTER = 365 * 24 * 3600


def time_series(players_rows: list[list], nr: dict) -> dict:
    """Moving averages over time for several players, on one shared x axis.

    In each series, None means "no game of this player at that time" (the
    chart connects across) except at the indices in "breaks", where the
    player paused for more than BREAK_AFTER (the chart leaves a gap there).
    Games without a usable date are left out.
    """
    values = []
    pauses = []
    for rows in players_rows:
        moving = moving_average(rows)
        v = {
            t: m
            for row, m in zip(rows, moving, strict=True)
            if (t := timestamp(row["date"], nr[row["game"]])) is not None
        }
        times = sorted(v)
        # one second after the last game before the pause
        pauses.append({a + 1 for a, b in pairwise(times) if b - a > BREAK_AFTER})
        values.append(v)
    x = sorted(set().union(*values, *pauses))
    index = {t: i for i, t in enumerate(x)}
    return {
        "x": x,
        "series": [[v.get(t) for t in x] for v in values],
        "breaks": [sorted(index[t] for t in p) for p in pauses],
    }


def player_charts(rows, by_date: bool = False) -> dict:
    """Series for the charts on a player page (drawn by uPlot).

    x: game number, or the time of the game (games without a usable date
    are left out of that chart).
    """
    if by_date:
        ts = time_series([rows], day_numbers(rows))
        x, moving, breaks = ts["x"], ts["series"][0], ts["breaks"][0]
    else:
        x = list(range(1, len(rows) + 1))
        moving, breaks = moving_average(rows), []
    return {
        "moving": {
            "window": MOVING_WINDOW,
            "by_date": by_date,
            "x": x,
            "date": [row["date"] for row in rows] if not by_date else [],
            "average": moving,
            "breaks": breaks,
        },
        "histogram": histogram(rows),
    }


def ahead(a: int, b: int) -> bool:
    """Did score a finish ahead of score b in the same game?"""
    return points(a) < points(b) or (a == WINNER and b != WINNER)


def compare(players: list[tuple[str, list]]) -> dict:
    """Side by side stats of several players (name, chronological rows).

    "together" counts only the games in which all of them played.
    """
    shared = set.intersection(*({row["game"] for row in rows} for _, rows in players))
    result = {
        "shared": len(shared),
        "overall": [
            {"name": name, **summarize([row["score"] for row in rows])}
            for name, rows in players
        ],
        "together": [
            {
                "name": name,
                **summarize([row["score"] for row in rows if row["game"] in shared]),
            }
            for name, rows in players
        ],
        "head_to_head": None,
        "seating": None,
    }
    if len(players) != 2 or not shared:
        return result

    (name_a, rows_a), (name_b, rows_b) = players
    a = {row["game"]: row for row in rows_a if row["game"] in shared}
    b = {row["game"]: row for row in rows_b if row["game"] in shared}
    result["head_to_head"] = {
        "a": name_a,
        "b": name_b,
        "a_ahead": sum(ahead(a[g]["score"], b[g]["score"]) for g in shared),
        "b_ahead": sum(ahead(b[g]["score"], a[g]["score"]) for g in shared),
        "a_wins": sum(a[g]["score"] == WINNER for g in shared),
        "b_wins": sum(b[g]["score"] == WINNER for g in shared),
    }

    # the old site's "anti-rumor": does it matter how far apart they sit?
    # distance = seats from a to b in seating order
    by_distance = defaultdict(lambda: ([], []))
    for g in shared:
        size = a[g]["number_of_players"]
        distance = (b[g]["position"] - a[g]["position"]) % size
        by_distance[distance][0].append(a[g]["score"])
        by_distance[distance][1].append(b[g]["score"])
    average_a = result["together"][0]["average"]
    average_b = result["together"][1]["average"]
    result["seating"] = [
        {
            "distance": distance,
            "games": len(sa),
            "players": [
                seat_stats(sa, average_a),
                seat_stats(sb, average_b),
            ],
        }
        for distance, (sa, sb) in sorted(by_distance.items())
    ]
    # symmetric y range of the seating chart, in steps of 10 points
    extent = max(
        (
            abs(p["diff"]) + (p["ci"] or 0)
            for s in result["seating"]
            for p in s["players"]
        ),
        default=0,
    )
    result["seating_range"] = max(10, 10 * math.ceil(extent / 10))
    return result


def seat_stats(scores: list[int], average: float) -> dict:
    """Points per game at one seating distance, compared to the average.

    ci: half width of the 95% confidence interval of the mean (normal
    approximation, 1.96 standard errors); None for a single game. The
    uncertainty of the average itself is small (many more games) and left
    out.
    """
    s = summarize(scores)
    n = s["games"]
    diff = s["average"] - average
    ci = 1.96 * s["sigma"] / math.sqrt(n - 1) if n > 1 else None
    # table tint: fewer points than usual is better
    level = sum(abs(diff) >= limit for limit in (2, 5, 10))
    tint = f"{'better' if diff < 0 else 'worse'}-{level}" if level else ""
    return {"average": s["average"], "diff": diff, "ci": ci, "tint": tint}


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Correlation coefficient r, None if it can't be computed."""
    if len(xs) < 3:
        return None
    try:
        return correlation(xs, ys)
    except StatisticsError:  # one of them constant
        return None


def correlations(players: list[tuple[str, list]]) -> dict:
    """Correlation of the points of each pair of players (name, rows).

    Over the games both played. ci: 95% interval of r (Fisher
    transformation); "tint" is only set when the interval excludes 0.
    """
    by_player = [
        {row["game"]: points(row["score"]) for row in rows} for _, rows in players
    ]
    cells = {}
    for i, a in enumerate(by_player):
        for j in range(i + 1, len(by_player)):
            b = by_player[j]
            shared = sorted(a.keys() & b.keys())
            xs = [a[g] for g in shared]
            ys = [b[g] for g in shared]
            r = pearson(xs, ys)
            low = high = None
            tint = ""
            if r is not None and len(xs) > 3 and abs(r) < 1:
                z = math.atanh(r)
                half = 1.96 / math.sqrt(len(xs) - 3)
                # rounded (+ 0.0 turns -0.0 into 0.0, no "-0.00" on the page)
                low = round(math.tanh(z - half), 2) + 0.0
                high = round(math.tanh(z + half), 2) + 0.0
                if low > 0 or high < 0:
                    level = 1 + sum(abs(r) >= limit for limit in (0.2, 0.4))
                    tint = f"corr-{'pos' if r > 0 else 'neg'}-{level}"
            cells[i, j] = cells[j, i] = {
                "games": len(xs),
                "r": r,
                "low": low,
                "high": high,
                "tint": tint,
                "scatter": list(zip(xs, ys, strict=True)),
            }
    n = len(players)
    return {
        "matrix": [[cells.get((i, j)) for j in range(n)] for i in range(n)],
        "pair": cells.get((0, 1)) if n == 2 else None,
    }


DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def timestamp(date: str, nr: int) -> int | None:
    """Unix time for the nr-th game of a day (one hour apart).

    Day or month 00 (unknown) count as 01; unparsable dates give None.
    """
    match = DATE.fullmatch(date)
    if not match:
        return None
    year, month, day = (int(x) for x in match.groups())
    try:
        start = datetime(year, max(month, 1), max(day, 1), tzinfo=UTC)
    except ValueError:
        return None
    return int(start.timestamp()) + 3600 * nr


def compare_charts(
    players: list[tuple[str, list]], together: bool, by_date: bool
) -> dict:
    """Chart series for the compare page.

    together: only the games in which all of them played.
    by_date: x = time of the game (games of a day an hour apart),
    otherwise x = game number (each player's own count).
    """
    if together:
        shared = set.intersection(
            *({row["game"] for row in rows} for _, rows in players)
        )
        players = [
            (name, [row for row in rows if row["game"] in shared])
            for name, rows in players
        ]

    if by_date:
        nr = day_numbers(row for _, rows in players for row in rows)
        ts = time_series([rows for _, rows in players], nr)
        x, series, breaks = ts["x"], ts["series"], ts["breaks"]
    else:
        length = max((len(rows) for _, rows in players), default=0)
        x = list(range(1, length + 1))
        series = [
            moving_average(rows) + [None] * (length - len(rows)) for _, rows in players
        ]
        breaks = [[] for _ in players]

    hists = [histogram(rows) for _, rows in players]
    return {
        "window": MOVING_WINDOW,
        "together": together,
        "by_date": by_date,
        "names": [name for name, _ in players],
        "x": x,
        "series": series,
        "breaks": breaks,
        "histogram": {
            "labels": hists[0]["labels"] if hists else [],
            # share of the player's games, so players with few games compare
            "percent": [
                [round(100 * c / max(sum(h["counts"]), 1), 1) for c in h["counts"]]
                for h in hists
            ],
        },
    }


@dataclass
class Sort:
    """Table sorting from ?sort=<column>&order=asc|desc.

    columns: column key -> True if it sorts descending by default
    (numbers, dates) or False (names).
    """

    columns: dict[str, bool]
    default: str

    def __post_init__(self):
        self.key = request.args.get("sort", self.default)
        if self.key not in self.columns:
            self.key = self.default
        order = request.args.get("order")
        self.desc = (
            self.columns[self.key]
            if order not in ("asc", "desc")
            else (order == "desc")
        )

    def apply(self, rows: list[dict]) -> list[dict]:
        def key(row):
            value = row[self.key]
            if isinstance(value, str):
                value = value.lower()
            return (value is None, value)

        # stable: rows keep their previous order (date) among equal values
        return sorted(rows, key=key, reverse=self.desc)

    def url(self, key: str) -> str:
        desc = not self.desc if key == self.key else self.columns[key]
        args = request.args.to_dict() | {
            "sort": key,
            "order": "desc" if desc else "asc",
        }
        return url_for(request.endpoint, **request.view_args, **args)

    def aria(self, key: str) -> str | None:
        if key != self.key:
            return None
        return "descending" if self.desc else "ascending"
