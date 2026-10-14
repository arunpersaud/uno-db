"""Skill ratings with openskill (Plackett-Luce model, like TrueSkill).

All games are replayed in date order. Each game is a ranking of the
players at the table: the winner first, then (mode "points") the others by
their points, fewest first, equal points tied; or (mode "winner") all
others tied for second.

Before each game the model also predicts every player's chance to win;
comparing that with the actual winner tells how well a mode predicts.
The shown rating is the conservative estimate mu - 3 sigma ("ordinal").
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as Date

from openskill.models import PlackettLuce

from .db import WINNER

MODES = ("winner", "points")
BURN_IN = 200  # games before predictions count (ratings still settling)
# How much a single game varies ("luck"). openskill's default (25/6) is made
# for games with more skill; with it the predictions were worse than
# chance. Tested on the 2003-2017 games: 25-40 predict best for both modes
# (2026-10-14), so UNO is mostly luck.
BETA = 30.0
PAUSE_DAYS = 180  # after a pause this long, a player's sigma grows again
PAUSE_GROWTH = 2.0  # sigma added per year of pause (in quadrature)


@dataclass
class Result:
    ratings: dict = field(default_factory=dict)  # player id -> rating
    names: dict = field(default_factory=dict)
    games: dict = field(default_factory=lambda: defaultdict(int))
    history: dict = field(default_factory=lambda: defaultdict(list))
    predictions: list = field(default_factory=list)  # (players, p_winner, top)


def parse_date(text: str) -> Date | None:
    try:
        year, month, day = (int(x) for x in text.split("-"))
        return Date(year, max(month, 1), max(day, 1))
    except ValueError:
        return None


def replay(
    rows, mode: str = "winner", pauses: bool = False, beta: float = BETA
) -> Result:
    """rows: stats.all_scores() (chronological).

    pauses: let sigma grow after long breaks (tested: predicts slightly
    worse, so off by default).
    """
    model = PlackettLuce(beta=beta)
    result = Result()
    last_played = {}
    by_game = defaultdict(list)
    order = []
    for row in rows:
        if row["game"] not in by_game:
            order.append(row["game"])
        by_game[row["game"]].append(row)

    for number, game in enumerate(order):
        table = by_game[game]
        if len(table) < 2:
            continue
        day = parse_date(table[0]["date"])
        teams = []
        for row in table:
            p = row["player"]
            rating = result.ratings.get(p) or model.rating()
            if pauses and day and p in last_played:
                gap = (day - last_played[p]).days
                if gap > PAUSE_DAYS:
                    grow = PAUSE_GROWTH * gap / 365
                    rating.sigma = min(math.hypot(rating.sigma, grow), 25 / 3)
            teams.append([rating])
            result.names[p] = row["name"]

        winners = [i for i, row in enumerate(table) if row["score"] == WINNER]
        if len(winners) == 1 and number >= BURN_IN:
            chances = model.predict_win(teams)
            top = max(range(len(chances)), key=chances.__getitem__)
            hit = top == winners[0]
            result.predictions.append((len(table), chances[winners[0]], hit))

        if mode == "points":
            ranks = [-1 if row["score"] == WINNER else row["score"] for row in table]
        else:
            ranks = [0 if row["score"] == WINNER else 1 for row in table]
        updated = model.rate(teams, ranks=ranks)
        for row, [rating] in zip(table, updated, strict=True):
            p = row["player"]
            result.ratings[p] = rating
            result.games[p] += 1
            result.history[p].append((row["date"], game, rating.ordinal()))
            if day:
                last_played[p] = day
    return result


def evaluate(result: Result) -> dict:
    """How well the predictions before each game matched the winners.

    log_loss: mean -ln(chance given to the actual winner), lower is better;
    chance_log_loss: the same for guessing 1/N; skill: 1 - ratio (0 = no
    better than guessing); favorite: share of games the favorite won.
    """
    n = len(result.predictions)
    if not n:
        return {"games": 0}
    log_loss = -sum(math.log(max(p, 1e-9)) for _, p, _ in result.predictions) / n
    chance = sum(math.log(size) for size, _, _ in result.predictions) / n
    return {
        "games": n,
        "log_loss": log_loss,
        "chance_log_loss": chance,
        "skill": 1 - log_loss / chance,
        "favorite": sum(top for _, _, top in result.predictions) / n,
        "chance_favorite": sum(1 / size for size, _, _ in result.predictions) / n,
    }


_cache: dict = {}


def cached(rows, mode: str) -> Result:
    """replay(), kept until the data (or the mode) changes."""
    key = (mode, hash(tuple((r["game"], r["player"], r["score"]) for r in rows)))
    if key not in _cache:
        if len(_cache) > 20:
            _cache.clear()
        _cache[key] = replay(rows, mode)
    return _cache[key]


def table(result: Result, min_games: int) -> list[dict]:
    """Players by rating (ordinal = mu - 3 sigma), best first."""
    rows = [
        {
            "player": p,
            "name": result.names[p],
            "rating": r.ordinal(),
            "mu": r.mu,
            "sigma": r.sigma,
            "games": result.games[p],
        }
        for p, r in result.ratings.items()
        if result.games[p] >= min_games
    ]
    rows.sort(key=lambda row: -row["rating"])
    return rows


def points_vs_table(rows) -> dict:
    """Average points per game compared to the others at the same table.

    For each game: a player's points minus the average of the others
    (black-card games count half, since those scores are doubled in
    "Uno default"); games with fewer than 3 players are left out. Negative
    is better. ci: half width of the 95% interval.

    Tested on the 2003-2017 games (2026-10-14): stable per player (odd vs.
    even games r = 0.36) and as good at predicting a game's order as the
    openskill ratings; the differences between the regulars are a few
    points per game.
    """
    from statistics import fmean, stdev

    tables = defaultdict(list)
    for row in rows:
        tables[row["game"]].append(row)
    relative = defaultdict(list)
    for table in tables.values():
        if len(table) < 3:
            continue
        points = [
            (0 if r["score"] == WINNER else r["score"]) / (2 if r["black"] else 1)
            for r in table
        ]
        total = sum(points)
        for row, p in zip(table, points, strict=True):
            relative[row["player"]].append(p - (total - p) / (len(points) - 1))
    return {
        player: {
            "average": fmean(values),
            "ci": 1.96 * stdev(values) / math.sqrt(len(values))
            if len(values) > 1
            else None,
        }
        for player, values in relative.items()
    }
