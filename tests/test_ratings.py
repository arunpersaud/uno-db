import re

import pytest

from unodb import ratings
from unodb.db import WINNER


def row(game, player, score, black=0, date="2004-01-01", session=1):
    return {
        "game": game,
        "session": session,
        "player": player,
        "name": f"P{player}",
        "score": score,
        "black": black,
        "date": date,
    }


def test_relative_points():
    # game 1 ended with a black card (the flag is per game)
    rows = [row(1, 1, WINNER, 1), row(1, 2, 10, 1), row(1, 3, 20, 1)]
    rows += [row(2, 1, 5), row(2, 2, WINNER)]  # two players: left out
    rel = ratings.relative_points(rows)
    # black card: everyone's points count half: 0, 5, 10
    assert [v for _, _, v in rel[1]] == [7.5]  # others 5 and 10 -> 7.5 - 0
    assert [v for _, _, v in rel[3]] == [-7.5]
    assert len(rel[2]) == 1


def test_few_games_are_pulled_toward_zero():
    sigma2, tau2 = 900.0, 1.0
    few = ratings.estimate([-20.0] * 10, sigma2, tau2)
    many = ratings.estimate([3.0] * 900, sigma2, tau2)
    assert few["keep"] == pytest.approx(1 / (1 + 90))
    assert abs(few["rating"]) < 0.3  # -20 over 10 games is mostly luck
    assert many["keep"] == pytest.approx(0.5)
    assert many["rating"] == pytest.approx(1.5)
    assert many["ci"] < few["ci"]


def test_spreads_from_regulars(monkeypatch):
    monkeypatch.setattr(ratings, "REGULAR", 3)
    rel = {
        1: [("d", g, 10.0) for g in range(3)],
        2: [("d", g, -10.0) for g in range(3)],
    }
    sigma2, tau2 = ratings.spreads(rel)
    assert sigma2 == pytest.approx(100.0)
    # means 10 and -10 (variance 100) minus noise 100/3
    assert tau2 == pytest.approx(100 - 100 / 3)


def test_ratings_page(client):
    html = client.get("/ratings").text
    assert "<h1>Ratings</h1>" in html
    # the fixture has 2 games with 3 players; everyone has fewer than 10
    assert 'href="/player/ann"' not in html
    assert 'data-src="/ratings.json"' in html


def test_ratings_table_and_chart(client, monkeypatch):
    from unodb import views

    monkeypatch.setattr(views, "RATING_MIN_GAMES", 1)
    html = client.get("/ratings").text
    names = re.findall(r'<a href="/player/([a-z-]+)">', html)
    # Ann had fewer points than the table in both 3-player games
    assert names[:3] == ["ann", "bob", "cy-young"]
    html = client.get("/ratings?sort=games&order=desc").text
    assert 'aria-sort="descending"><a href="/ratings?sort=games&amp;order=asc"' in html
    data = client.get("/ratings.json").get_json()
    assert data["names"] == ["Ann", "Bob", "Cy Young"]
    assert len(data["series"]) == 3
    assert re.search(r"#1 of 3</a>", client.get("/player/ann").text)
