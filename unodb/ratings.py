"""Ratings: how many points per game a player does better than the table.

For each game with at least 3 players: the average points of the others at
the table minus the player's own points (positive = fewer points than the
others = better). Black-card games count half, since their scores are
doubled in "Uno default".

A player's plain average of this is mostly luck when they have few games
(a single game varies by about +-30 points). The rating therefore pulls
the average toward 0 by as much as their number of games can't vouch for
("shrinkage", empirical Bayes): with spread tau of the real differences
between players and per-game spread sigma, a player with n games keeps
the share tau^2 / (tau^2 + sigma^2 / n) of their average. tau is estimated
from the players with at least REGULAR games.

Tested on the 2003-2017 games (2026-10-14): sigma ~29 points, tau ~1 point,
so a single game is mostly luck but the regulars differ clearly over
hundreds of games. This predicted the order within a game as well as
openskill ratings (both rank correlation ~0.05), which were dropped as
harder to read.
"""

import math
from collections import defaultdict
from statistics import fmean, pstdev, pvariance

from . import stats as st
from .db import WINNER

REGULAR = 100  # games, to estimate the real spread between players
MIN_TAU2 = 0.25  # lower bound for the estimated spread (squared points)
Z95 = 1.96


def relative_points(rows) -> dict[int, list[tuple[str, int, float]]]:
    """player -> [(date, game, points better than the table)] in order."""
    tables = defaultdict(list)
    for row in rows:
        tables[row["game"]].append(row)
    result = defaultdict(list)
    for table in tables.values():  # rows are chronological, so are tables
        if len(table) < 3:
            continue
        points = [
            (0 if r["score"] == WINNER else r["score"]) / (2 if r["black"] else 1)
            for r in table
        ]
        total = sum(points)
        for row, p in zip(table, points, strict=True):
            others = (total - p) / (len(points) - 1)
            result[row["player"]].append((row["date"], row["game"], others - p))
    return result


def spreads(relative: dict) -> tuple[float, float]:
    """(sigma^2 per game, tau^2 between players)."""
    values = [v for games in relative.values() for _, _, v in games]
    if len(values) < 2:
        return 1.0, MIN_TAU2
    sigma2 = pstdev(values) ** 2
    regulars = [g for g in relative.values() if len(g) >= REGULAR]
    if len(regulars) < 2:
        return sigma2, MIN_TAU2
    means = [fmean(v for _, _, v in g) for g in regulars]
    noise = fmean(sigma2 / len(g) for g in regulars)
    return sigma2, max(pvariance(means) - noise, MIN_TAU2)


def estimate(values: list[float], sigma2: float, tau2: float) -> dict:
    """Rating (shrunk average) with 95% interval, from a player's values."""
    n = len(values)
    average = fmean(values)
    se2 = sigma2 / n
    keep = tau2 / (tau2 + se2)
    return {
        "games": n,
        "average": average,
        "rating": average * keep,
        "ci": Z95 * math.sqrt(tau2 * se2 / (tau2 + se2)),
        "keep": keep,
    }


def table(rows, min_games: int = 1) -> list[dict]:
    """Players by rating, best first, with their place."""
    relative = relative_points(rows)
    sigma2, tau2 = spreads(relative)
    names = {row["player"]: row["name"] for row in rows}
    result = [
        {"player": p, "name": names[p], **estimate([v for _, _, v in g], sigma2, tau2)}
        for p, g in relative.items()
        if len(g) >= min_games
    ]
    result.sort(key=lambda r: -r["rating"])
    for place, row in enumerate(result, 1):
        row["place"] = place
    return result


def history(rows, players: list[int]) -> dict:
    """The rating of the given players after each of their games, on a
    shared date axis (see stats.with_breaks)."""
    relative = relative_points(rows)
    sigma2, tau2 = spreads(relative)
    nr = st.day_numbers(rows)
    values = []
    for player in players:
        series, so_far = {}, []
        for date, game, value in relative.get(player, []):
            so_far.append(value)
            t = st.timestamp(date, nr[game])
            if t is not None:
                series[t] = round(estimate(so_far, sigma2, tau2)["rating"], 3)
        values.append(series)
    return st.with_breaks(values)
