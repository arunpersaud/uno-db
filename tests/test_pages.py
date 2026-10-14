import re
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "url",
    ["/", "/sessions", "/session/2004-05-28", "/players", "/player/ann", "/contribute"],
)
def test_pages(client, url):
    assert client.get(url).status_code == 200


def test_index(client):
    html = client.get("/").text
    assert "4 games in 3 sessions" in html
    assert "A total of 10 scores" in html
    assert "Lowest scoring game ever: 3.50" in html
    assert "Lowest scoring session: 3.50" in html  # a single game counts
    assert "Highest scoring session: 16.17" in html
    assert "2004-05-28 to 2004-06-01" in html


def test_session(client):
    html = client.get("/session/2004-05-28").text
    # columns in seating order, totals without the winner rows
    names = re.findall(r'<th><a href="/player/([a-z-]+)">([^<]+)</a></th>', html)
    assert names == [("ann", "Ann"), ("bob", "Bob"), ("cy-young", "Cy Young")]
    assert re.search(r"<th>Total</th>\s*<th>5</th>\s*<th>12</th>\s*<th>80</th>", html)
    assert re.search(r"<th>Wins</th>\s*<th>1</th>\s*<th>1</th>\s*<th>0</th>", html)
    assert html.count('class="winner"') == 2


def test_sessions_on_the_same_day(client):
    html = client.get("/session/2004-06-01").text
    assert html.count("<table") == 2
    assert "<h2>Berkeley</h2>" in html
    assert "<h2>Lodi</h2>" in html


@pytest.mark.parametrize("url", ["/session/1999-01-01", "/player/nobody"])
def test_not_found(client, url):
    assert client.get(url).status_code == 404


PLAYER_ROW = re.compile(
    r'<a href="/player/[a-z-]+">([^<]+)</a></td>\s*<td>(\d+)</td>\s*<td>(\d+)</td>'
)


def test_players(client):
    # default: last played (all the same here), then most wins, then name
    rows = PLAYER_ROW.findall(client.get("/players").text)
    assert rows == [("Ann", "3", "2"), ("Bob", "3", "2"), ("Cy Young", "4", "0")]


def test_players_sorted(client):
    html = client.get("/players?sort=games&order=desc").text
    assert PLAYER_ROW.findall(html)[0][0] == "Cy Young"
    assert 'aria-sort="descending"><a href="/players?sort=games&amp;order=asc"' in html
    # unknown columns fall back to the default
    assert client.get("/players?sort=__class__").status_code == 200


def test_sessions_sorted_by_average(client):
    html = client.get("/sessions?sort=average&order=asc").text
    averages = re.findall(r"<td>(\d+\.\d)</td>\s*</tr>", html)
    assert averages == ["3.5", "10.0", "16.2"]


def test_player(client):
    html = client.get("/player/cy-young").text
    assert "<h1>Cy Young</h1>" in html
    assert "4 games in 3 sessions" in html
    assert '<p class="hero">26.8</p>' in html  # points per game
    assert "1 games ended with a black card" in html
    # by group size: 2 games with 3 players, 2 with 2
    assert re.search(r"<td>2</td>\s*<td>2</td>\s*<td>0</td>", html)
    assert re.search(r"<td>3</td>\s*<td>2</td>\s*<td>0</td>", html)


def test_player_charts(client):
    data = client.get("/player/cy-young/charts.json").get_json()
    assert data["moving"]["x"] == [1, 2, 3, 4]
    assert data["moving"]["average"] == [None] * 4  # fewer than 20 games
    hist = dict(
        zip(data["histogram"]["labels"], data["histogram"]["counts"], strict=True)
    )
    assert hist["won"] == 0
    assert hist["0–9"] == hist["20–29"] == hist["30–39"] == hist["50–59"] == 1
    assert sum(hist.values()) == 4


def test_player_charts_by_date(client):
    data = client.get("/player/cy-young/charts.json?x=date").get_json()
    day1 = 1085702400  # 2004-05-28 UTC
    day2 = 1086048000  # 2004-06-01 UTC
    # games of a day an hour apart, also across two sessions on 2004-06-01
    assert data["moving"]["x"] == [day1, day1 + 3600, day2, day2 + 3600]


def test_black_card_mark(client):
    html = client.get("/session/2004-05-28").text
    assert html.count("✓</span>") == 1


def test_player_charts_redirect(client):
    response = client.get("/player/Cy%20Young/charts.json")
    assert response.location == "/player/cy-young/charts.json"


@pytest.mark.parametrize(
    "url", ["/player/Ann", "/player/Cy%20Young", "/player/CY-young"]
)
def test_player_canonical_url(client, url):
    response = client.get(url)
    assert response.status_code == 301
    assert response.location in ("/player/ann", "/player/cy-young")


def test_public_pages_are_read_only(app):
    from unodb.db import get_db

    with app.test_request_context("/"):
        app.preprocess_request()
        with pytest.raises(Exception, match="readonly"):
            get_db().execute("DELETE FROM players")


def test_missing_database(tmp_path):
    from unodb import create_app

    with pytest.raises(RuntimeError, match="not found"):
        create_app({"TESTING": True, "DATABASE": tmp_path / "nope.sqlite"})


def test_secret_key_required_in_production(database, monkeypatch):
    from unodb import create_app

    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        create_app({"DATABASE": database})


def test_security_headers(client):
    headers = client.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    csp = headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "unsafe" not in csp


def test_escaping(app, database):
    import sqlite3

    with sqlite3.connect(database) as db:
        db.execute("UPDATE players SET name = '<b>Ann</b>' WHERE id = 1")
    html = app.test_client().get("/session/2004-05-28").text
    assert "&lt;b&gt;Ann&lt;/b&gt;" in html


TEMPLATES = sorted(Path(__file__).parent.parent.glob("unodb/templates/*.html"))


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_no_inline_code(template):
    """The CSP blocks inline scripts, styles and event handlers."""
    html = template.read_text()
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "<style" not in html
    assert not re.search(r"\sstyle=", html)
    assert not re.search(r"\son[a-z]+=", html)


def test_compare_empty(client):
    html = client.get("/compare/").text
    assert "Pick at least two players" in html


def test_compare(client):
    response = client.get("/compare/ann/bob")
    assert response.status_code == 200
    html = response.text
    assert "The 2 games together" in html
    assert "Ann finished ahead of Bob\n  1 times" in html
    # seating: Bob sat right after Ann in both shared games; Ann had 0 and 5
    # points there (her average), sigma 2.5 -> 95% interval 1.96 * 2.5 / 1
    assert re.search(r"<td>1</td>\s*<td>2</td>\s*<td[^>]*>2.5\s*\(\+0.0 ± 4.9\)", html)
    assert (
        "<title>Ann, distance 1: +0.0 ± 4.9 points per game (2 games)</title>" in html
    )
    assert response.headers["HX-Push-Url"] == "/compare/ann/bob"


@pytest.mark.parametrize(
    ("url", "location"),
    [
        ("/compare/Ann/bob/ann", "/compare/ann/bob"),
        ("/compare/ann?add=Bob", "/compare/ann/bob"),
        ("/compare/ann?add=Cy+Young&x=date", "/compare/ann/cy-young?x=date"),
        ("/compare/ann/bob?add=cy-young&games=together", None),
    ],
)
def test_compare_redirects(client, url, location):
    response = client.get(url)
    assert response.status_code in (301, 302)
    if location:
        assert response.location == location
    else:
        assert response.location == "/compare/ann/bob/cy-young?games=together"


def test_compare_add_unknown(client):
    response = client.get("/compare/ann?add=<b>Zed</b>")
    assert response.status_code == 200  # htmx only swaps in 2xx responses
    assert "There is no player called &lt;b&gt;Zed&lt;/b&gt;." in response.text


def test_compare_add_twice(client):
    html = client.get("/compare/ann?add=ANN").text
    assert "Ann is already in the comparison." in html


def test_compare_limit(client, monkeypatch):
    from unodb import views

    monkeypatch.setattr(views, "MAX_COMPARE", 2)
    html = client.get("/compare/ann/bob?add=cy-young").text
    assert "At most 2 players can be compared." in html
    assert client.get("/compare/ann/bob/cy-young").location == "/compare/ann/bob"


def test_compare_unknown_player(client):
    assert client.get("/compare/ann/nobody").status_code == 404


def test_compare_charts(client):
    data = client.get("/compare.json/ann/cy-young").get_json()
    assert data["names"] == ["Ann", "Cy Young"]
    assert data["x"] == [1, 2, 3, 4]  # Cy Young has 4 games, Ann 3
    assert len(data["series"][0]) == len(data["series"][1]) == 4

    data = client.get("/compare.json/ann/cy-young?games=together").get_json()
    assert data["x"] == [1, 2, 3]

    data = client.get("/compare.json/ann/bob?x=date").get_json()
    # games 1, 2 (together), 3 (Ann) and 4 (Bob): 2 on each day
    assert len(data["x"]) == 4
    assert data["x"] == sorted(data["x"])


@pytest.mark.parametrize("url", ["/compare.json/ann", "/compare.json/ann/nobody"])
def test_compare_charts_not_found(client, url):
    assert client.get(url).status_code == 404


def test_static_urls_are_versioned(client):
    html = client.get("/").text
    match = re.search(r'src="/static/charts\.js\?v=([0-9a-f]{12})"', html)
    assert match
    response = client.get(f"/static/charts.js?v={match[1]}")
    assert "max-age=31536000" in response.headers["Cache-Control"]
    assert "immutable" in response.headers["Cache-Control"]
    assert "no-cache" in client.get("/static/charts.js").headers["Cache-Control"]


@pytest.mark.parametrize(
    "url", ["/compare/ann/bob?x=date&games=together", "/player/ann?x=date"]
)
def test_switches_can_be_turned_off(client, url):
    """The switch form's URL has no options, only the checked switches add them."""
    html = client.get(url).text
    form = re.search(r'<form class="options"[^>]*>', html)[0]
    assert re.search(r'hx-get="/(compare|player)/[a-z/]+"', form)
    assert "?" not in form


def suggestions(html):
    block = re.search(r'<p class="suggestions">(.*?)</p>', html, re.S)
    return re.findall(r">([^<]+)</a>", block[1]) if block else []


def test_compare_suggestions_stay(client):
    assert suggestions(client.get("/compare/").text) == ["Cy Young", "Ann", "Bob"]
    # picked players drop out, the others stay (also with two picked)
    assert suggestions(client.get("/compare/ann").text) == ["Cy Young", "Bob"]
    assert suggestions(client.get("/compare/ann/bob").text) == ["Cy Young"]


def test_compare_correlation_matrix(client):
    html = client.get("/compare/ann/bob/cy-young").text
    assert '<table class="numbers correlation">' in html
    # Ann 0, 5, 0 and Cy Young 30, 50, 7 points in their 3 games together
    assert "+0.85</a>\n          <br><small>3 games</small>" in html


def test_compare_correlation_scatter(client):
    html = client.get("/compare/ann/cy-young").text
    assert '<svg class="scatter"' in html
    assert html.count('r="3"></circle>') == 3
    assert "Correlation r = 0.85" in html


def test_csv_exports(client):
    response = client.get("/session/2004-06-01.csv")
    assert response.mimetype == "text/csv"
    assert 'filename="uno-2004-06-01.csv"' in response.headers["Content-Disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0] == (
        "date,location,game_type,session,game,player,seat,points,won,black_card"
    )
    # two sessions that day, one game each; Ann won game 1 of session 2
    assert "2004-06-01,Berkeley,Uno default,2,1,Ann,1,0,1,0" in lines
    assert "2004-06-01,Lodi,Uno default,3,1,Cy Young,2,20,0,0" in lines

    lines = client.get("/scores.csv").text.strip().splitlines()
    assert len(lines) == 1 + 10
    # session 1 has two games
    assert "2004-05-28,Berkeley,Uno default,1,2,Cy Young,3,50,0,1" in lines

    lines = client.get("/sessions.csv").text.strip().splitlines()
    assert lines[1] == "2004-06-01,Lodi,Uno default,2,1,10.0"

    lines = client.get("/player/cy-young/sessions.csv").text.strip().splitlines()
    assert lines[-1] == "2004-05-28,Berkeley,Uno default,3,2,0,80,40.0"

    assert client.get("/session/1999-01-01.csv").status_code == 404
    assert 'href="/session/2004-06-01.csv' in client.get("/session/2004-06-01").text


def test_csv_formula_injection():
    from unodb.export import cell

    assert cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert cell("-2+3") == "'-2+3"
    assert cell("Joe") == "Joe"
    assert cell(-5) == -5


@pytest.mark.parametrize(
    ("url", "text"),
    [
        ("/robots.txt", "Disallow: /admin/"),
        ("/humans.txt", "Arun Persaud"),
        ("/llms.txt", "# The UNO database"),
        ("/.well-known/security.txt", "Contact: mailto:arun@nubati.net"),
    ],
)
def test_root_files(client, url, text):
    response = client.get(url)
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert text in response.text


def test_security_txt_expires_within_a_year(client):
    from datetime import UTC, datetime

    expires = re.search(
        r"Expires: (\S+)", client.get("/.well-known/security.txt").text
    )[1]
    days = (datetime.fromisoformat(expires) - datetime.now(UTC)).days
    assert 300 < days <= 365


def test_favicon(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.mimetype == "image/png"


def test_request_size_limit(client):
    assert client.post("/admin/login/options", data="x" * 100_000).status_code == 413


def test_player_without_games_is_gone(app, client):
    from unodb.db import get_db

    with app.app_context():
        get_db().execute("UPDATE session SET deleted = 'now'")
    assert client.get("/player/ann").status_code == 404


def test_hsts_only_with_https(database):
    from unodb import create_app

    https = create_app(
        {"TESTING": True, "DATABASE": database, "ORIGIN": "https://x.org"}
    )
    header = https.test_client().get("/").headers["Strict-Transport-Security"]
    assert header == "max-age=31536000; includeSubDomains"
    http = create_app({"TESTING": True, "DATABASE": database})
    assert "Strict-Transport-Security" not in http.test_client().get("/").headers
