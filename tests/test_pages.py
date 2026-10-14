import re
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "url", ["/", "/sessions", "/session/2004-05-28", "/players", "/player/ann"]
)
def test_pages(client, url):
    assert client.get(url).status_code == 200


def test_index(client):
    html = client.get("/").text
    assert "4 games in 3 sessions with" in html
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


def test_players(client):
    html = client.get("/players").text
    rows = re.findall(
        r'<a href="/player/[a-z-]+">([^<]+)</a></td>\s*'
        r"<td>(\d+)</td>\s*<td>(\d+)</td>",
        html,
    )
    assert rows == [("Cy Young", "4", "0"), ("Ann", "3", "2"), ("Bob", "3", "2")]


def test_player(client):
    html = client.get("/player/cy-young").text
    assert "<h1>Cy Young</h1>" in html
    assert "4 games, 0 wins" in html
    assert "26.8 points per game" in html


@pytest.mark.parametrize(
    "url", ["/player/Ann", "/player/Cy%20Young", "/player/CY-young"]
)
def test_player_canonical_url(client, url):
    response = client.get(url)
    assert response.status_code == 301
    assert response.location in ("/player/ann", "/player/cy-young")


def test_database_is_read_only(app):
    from unodb.db import get_db

    with app.app_context(), pytest.raises(Exception, match="readonly"):
        get_db().execute("DELETE FROM players")


def test_missing_database(tmp_path):
    from unodb import create_app

    with pytest.raises(RuntimeError, match="not found"):
        create_app({"DATABASE": tmp_path / "nope.sqlite"})


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


def test_old_links_go_to_php(client):
    response = client.get("/?name=Arun&mingames=0")
    assert response.status_code == 302
    assert response.location == "/index.php?name=Arun&mingames=0"
