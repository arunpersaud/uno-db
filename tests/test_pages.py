import re
from pathlib import Path

import pytest


@pytest.mark.parametrize("url", ["/", "/sessions", "/sessions/1"])
def test_pages(client, url):
    assert client.get(url).status_code == 200


def test_index(client):
    html = client.get("/").text
    assert "3 games in 2 sessions with" in html
    assert "2004-05-28 to 2004-06-01" in html


def test_session(client):
    html = client.get("/sessions/1").text
    # columns in seating order, totals without the winner rows
    assert re.search(r"<th>Ann</th>\s*<th>Bob</th>\s*<th>Cy</th>", html)
    assert re.search(r"<th>Total</th>\s*<th>5</th>\s*<th>12</th>\s*<th>80</th>", html)
    assert re.search(r"<th>Wins</th>\s*<th>1</th>\s*<th>1</th>\s*<th>0</th>", html)
    assert html.count('class="winner"') == 2


def test_unknown_session(client):
    assert client.get("/sessions/99").status_code == 404


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
    html = app.test_client().get("/sessions/1").text
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
