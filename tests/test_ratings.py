import re

import pytest

from unodb import ratings
from unodb.db import WINNER


def row(game, player, score, date="2004-01-01"):
    return {
        "game": game,
        "player": player,
        "name": f"P{player}",
        "score": score,
        "date": date,
    }


def games(n):
    """Player 1 always wins; player 2 always has fewer points than 3."""
    rows = []
    for g in range(n):
        rows += [row(g, 1, WINNER), row(g, 2, 5), row(g, 3, 50)]
    return rows


def test_winner_rises():
    r = ratings.replay(games(20), "winner")
    assert r.ratings[1].mu > r.ratings[2].mu
    # only the win counts: 2 and 3 stay equal
    assert r.ratings[2].mu == pytest.approx(r.ratings[3].mu)
    assert r.games[1] == 20
    assert len(r.history[1]) == 20


def test_points_rank_the_losers():
    r = ratings.replay(games(20), "points")
    assert r.ratings[1].mu > r.ratings[2].mu > r.ratings[3].mu


def test_predictions_after_burn_in(monkeypatch):
    monkeypatch.setattr(ratings, "BURN_IN", 5)
    r = ratings.replay(games(20))
    e = ratings.evaluate(r)
    assert e["games"] == 15
    assert e["favorite"] == 1.0  # player 1 is the favorite and always wins
    assert e["skill"] > 0
    assert ratings.evaluate(ratings.Result())["games"] == 0


def test_table_and_cache():
    rows = games(10)
    first = ratings.cached(rows, "winner")
    assert ratings.cached(rows, "winner") is first
    assert ratings.cached(rows, "points") is not first
    table = ratings.table(first, min_games=5)
    assert [t["player"] for t in table][0] == 1
    assert ratings.table(first, min_games=11) == []


def test_ratings_page(client, monkeypatch):
    from unodb import views

    monkeypatch.setattr(views, "RATING_MIN_GAMES", 1)
    html = client.get("/ratings").text
    assert "Ratings" in html and "How much is skill?" in html
    assert 'href="/player/ann"' in html
    assert 'data-src="/ratings.json"' in html
    html = client.get("/ratings?losers=points").text
    assert re.search(r'name="losers" value="points"\s+checked>', html)
    assert 'data-src="/ratings.json?losers=points"' in html
    data = client.get("/ratings.json").get_json()
    assert set(data["names"]) == {"Ann", "Bob", "Cy Young"}
    assert len(data["x"]) == len(data["series"][0])
    # Ann and Bob both won 2 of their 3 games, Cy Young none
    assert re.search(r"#[12] of 3</a> players", client.get("/player/ann").text)
    assert "#3 of 3</a> players" in client.get("/player/cy-young").text


def test_points_vs_table():
    # 3 players, 4 games: player 1 always 0 (won), 2 always 10, 3 always 20
    rows = []
    for g in range(4):
        rows += [
            {**row(g, 1, WINNER), "black": 0},
            {**row(g, 2, 10), "black": 0},
            {**row(g, 3, 20), "black": 1 if g == 0 else 0},
        ]
    vs = ratings.points_vs_table(rows)
    # player 1: 0 - mean(10, 20) = -15 (game 0: 0 - mean(10, 10) = -10)
    assert vs[1]["average"] == pytest.approx((-10 - 15 * 3) / 4)
    assert vs[2]["average"] > vs[1]["average"]
    assert vs[3]["average"] > 0
    assert vs[1]["ci"] > 0


def test_ratings_sortable(client, monkeypatch):
    from unodb import views

    monkeypatch.setattr(views, "RATING_MIN_GAMES", 1)
    html = client.get("/ratings?sort=vs_table_average").text
    assert (
        'aria-sort="ascending"><a href="/ratings?sort=vs_table_average&amp;order=desc"'
        in html
    )
    names = re.findall(r'<a href="/player/([a-z-]+)">', html)
    # games with 3 players (black card halved): Ann 0 vs. (12+30)/2 and
    # 2.5 vs. (0+25)/2 -> -15.5; Bob -3 and -13.75 -> -8.4; Cy Young above
    assert names[:3] == ["ann", "bob", "cy-young"]
