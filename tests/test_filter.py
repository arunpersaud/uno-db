import re

import pytest

from unodb.db import get_db


@pytest.fixture
def bruno(app):
    """Session 3 (one game: Bob won, Cy Young 20) was played as Black Rock Uno."""
    with app.app_context():
        get_db().execute("UPDATE session SET variation = 2 WHERE id = 3")


def test_filter_numbers(client, bruno):
    assert "4 games in 3 sessions" in client.get("/").text
    assert "1 games in 1 sessions" in client.get("/?variant=Bruno").text
    assert "3 games in 2 sessions" in client.get("/?variant=Uno").text
    # all types picked = no filter; unknown types are ignored
    assert "4 games in 3 sessions" in client.get("/?variant=Uno&variant=Bruno").text
    assert "4 games in 3 sessions" in client.get("/?variant=nope").text


def test_links_keep_the_filter(client, bruno):
    html = client.get("/players?variant=Bruno").text
    assert 'href="/player/bob?variant=Bruno"' in html
    assert 'href="/sessions?variant=Bruno"' in html
    # sorting keeps it too
    assert re.search(
        r'href="/players\?sort=games&amp;order=desc&amp;variant=Bruno"', html
    )
    # but not the rules pages
    assert 'href="/variants"' in html


def test_player_and_charts_filtered(client, bruno):
    html = client.get("/player/cy-young?variant=Uno").text
    assert "3 games in 2 sessions" in html
    assert 'data-src="/player/cy-young/charts.json?variant=Uno"' in html
    data = client.get("/player/cy-young/charts.json?variant=Uno").get_json()
    assert data["moving"]["x"] == [1, 2, 3]


def test_compare_filtered(client, bruno):
    html = client.get("/compare/bob/cy-young?variant=Bruno").text
    assert "The 1 games together" in html
    assert "/compare.json/bob/cy-young?variant=Bruno" in html


def test_filter_form(client):
    html = client.get("/sessions").text
    assert '<details class="variant-filter" >' in html
    assert "Game types: all" in html
    assert html.count('name="variant"') == 2
    html = client.get("/sessions?variant=Uno&sort=games").text
    assert "Game types: Uno default" in html
    assert '<input type="hidden" name="sort" value="games">' in html
    assert "variant-filter" not in client.get("/variants").text
