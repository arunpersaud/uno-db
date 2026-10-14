"""Statistics, computed in Python from plain rows.

The data is small (about 7500 scores), so each page fetches the rows it
needs once and aggregates them here. Points: a win counts as 0 (the winner
has the score WINNER in the database), as in the old PHP site.
"""

from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean, pstdev

from flask import request, url_for

from .db import WINNER, query

# sessions with fewer games are left out of the "highest/lowest" records
MIN_RECORD_GAMES = 3
MOVING_WINDOW = 20
HISTOGRAM_BIN = 10
HISTOGRAM_MAX = 150  # last bin: this and more

SCORES_SQL = """
SELECT session.id AS session, session.date, session.number_of_players,
       locations.name AS location, variations.name AS variation,
       games.id AS game, games.end_with_black_card AS black,
       scores.player, players.name, scores.score
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
    counted = [s for s in session_list if s["games"] >= MIN_RECORD_GAMES]

    def by_average(entry):
        return entry["average"]

    return {
        "high_session": max(counted, key=by_average, default=None),
        "low_session": min(counted, key=by_average, default=None),
        "high_game": max(game_list, key=by_average, default=None),
        "low_game": min(game_list, key=by_average, default=None),
        "min_games": MIN_RECORD_GAMES,
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
    summary["first"] = rows[0]["date"] if rows else None
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
    counted = [s for s in session_list if s["games"] >= MIN_RECORD_GAMES]
    summary["best_session"] = min(counted, key=lambda s: s["average"], default=None)
    summary["worst_session"] = max(counted, key=lambda s: s["average"], default=None)

    return {"summary": summary, "group_sizes": group_sizes, "sessions": session_list}


def player_charts(rows) -> dict:
    """Series for the charts on a player page (drawn by uPlot)."""
    pts = [points(row["score"]) for row in rows]
    moving = [
        round(fmean(pts[i + 1 - MOVING_WINDOW : i + 1]), 2)
        if i + 1 >= MOVING_WINDOW
        else None
        for i in range(len(pts))
    ]

    # histogram: wins, then bins of HISTOGRAM_BIN points (0-9, 10-19, ...)
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

    return {
        "moving": {
            "window": MOVING_WINDOW,
            "game": list(range(1, len(pts) + 1)),
            "date": [row["date"] for row in rows],
            "average": moving,
        },
        "histogram": {"labels": labels, "counts": counts},
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
