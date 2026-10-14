import pytest

from unodb import stats
from unodb.db import WINNER


def test_summarize():
    s = stats.summarize([WINNER, 10, 20, WINNER])
    assert s["games"] == 4
    assert s["wins"] == 2
    assert s["win_rate"] == 0.5
    assert s["points"] == 30
    assert s["average"] == 7.5
    assert s["sigma"] == pytest.approx(8.29, abs=0.01)  # population sigma


def test_summarize_empty():
    assert stats.summarize([])["average"] == 0.0


def row(game, score, session=1, date="2004-01-01", players=3):
    return {
        "session": session,
        "date": date,
        "location": "Lodi",
        "variation": "Uno default",
        "variation_short": "Uno",
        "created_by": None,
        "number_of_players": players,
        "game": game,
        "black": 0,
        "player": 1,
        "name": "Ann",
        "score": score,
        "table_size": players,
    }


def test_player_streak_and_sessions():
    rows = [row(1, WINNER), row(2, WINNER), row(3, 5), row(4, WINNER)]
    rows += [row(5, 40, session=2, date="2004-02-01", players=4)]
    data = stats.player(rows)
    assert data["summary"]["streak"] == 2
    assert data["summary"]["highest"] == 40
    assert data["summary"]["best_session"]["id"] == 1  # 5 points in 4 games
    assert data["summary"]["worst_session"]["id"] == 2  # 40 points in 1 game
    assert [g["size"] for g in data["group_sizes"]] == [3, 4]


def test_histogram_last_bin():
    rows = [row(1, 149), row(2, 150), row(3, 400)]
    hist = stats.player_charts(rows)["histogram"]
    counts = dict(zip(hist["labels"], hist["counts"], strict=True))
    assert counts["140–149"] == 1
    assert counts["150+"] == 2


def test_moving_average():
    rows = [row(i, i) for i in range(1, 22)]
    moving = stats.player_charts(rows)["moving"]["average"]
    assert moving[:19] == [None] * 19
    assert moving[19] == 10.5  # mean of 1..20
    assert moving[20] == 11.5


def test_records():
    sessions = [
        {"id": 1, "games": 3, "average": 20.0},
        {"id": 2, "games": 5, "average": 10.0},
        {"id": 3, "games": 1, "average": 99.0},  # one game counts too
    ]
    games = [{"id": 7, "average": 5.0}, {"id": 8, "average": 50.0}]
    r = stats.records(sessions, games)
    assert r["high_session"]["id"] == 3
    assert r["low_session"]["id"] == 2
    assert r["high_game"]["id"] == 8
    assert r["low_game"]["id"] == 7


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        ("2004-05-28", 1085702400),
        ("2003-06-00", 1054425600),  # unknown day -> 1st of the month
        ("1???-??-??", None),
        ("2003-02-30", None),
    ],
)
def test_timestamp(date, expected):
    assert stats.timestamp(date, 0) == expected


def test_ahead():
    assert stats.ahead(WINNER, 0)  # a win beats 0 points
    assert not stats.ahead(0, WINNER)
    assert stats.ahead(3, 10)
    assert not stats.ahead(10, 10)


def test_correlations_interval():
    # perfectly related points over 10 games: r = 1, no Fisher interval
    rows_a = [row(g, g) for g in range(10)]
    rows_b = [row(g, 2 * g) for g in range(10)]
    c = stats.correlations([("A", rows_a), ("B", rows_b)])
    assert c["pair"]["r"] == pytest.approx(1.0)
    assert c["matrix"][0][0] is None

    # noisy but clearly positive: colored, interval above 0
    rows_b = [row(g, g + (3 if g % 2 else -3)) for g in range(10)]
    pair = stats.correlations([("A", rows_a), ("B", rows_b)])["pair"]
    assert 0 < pair["low"] < pair["r"] < pair["high"]
    assert pair["tint"].startswith("corr-pos-")


def test_win_ratio():
    # a win in a 2-player game (chance 1/2), a win and two losses in
    # 4-player games (chance 1/4 each): 2 wins, 1/2 + 3/4 = 1.25 expected
    rows = [row(1, WINNER, players=2), row(2, WINNER, players=4)]
    rows += [row(3, 10, players=4), row(4, 5, players=4)]
    s = stats.summarize_rows(rows)
    assert s["expected_wins"] == pytest.approx(1.25)
    assert s["win_ratio"] == pytest.approx(1.6)


def test_breaks_cover_the_whole_pause():
    year = 365 * 24 * 3600
    a = {0: 1.0, 10: 2.0, 3 * year: 3.0}  # pause of almost 3 years
    b = {5: 1.0, year: 2.0, 2 * year: 2.5, 3 * year: 3.0}  # plays in between
    data = stats.with_breaks([a, b])
    x = data["x"]
    assert x == [0, 5, 10, 11, year, 2 * year, 3 * year]
    # a: every point between its game at 10 and the one 3 years later
    assert [x[i] for i in data["breaks"][0]] == [11, year, 2 * year]
    assert data["breaks"][1] == []
    assert data["series"][0] == [1.0, None, 2.0, None, None, None, 3.0]
