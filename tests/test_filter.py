import re

import pytest

from unodb.db import get_db


@pytest.fixture
def bruno(app):
    """Session 3 (one game: Bob won, Cy Young 20) was played as Black Rock Uno."""
    with app.app_context():
        get_db().execute("UPDATE session SET variation = 2 WHERE id = 3")


def test_filter_numbers(client, bruno):
    # one game type at a time; the one with most sessions is the default
    assert "3 games in 2 sessions" in client.get("/").text
    assert "1 games in 1 sessions" in client.get("/?variant=Bruno").text
    assert "3 games in 2 sessions" in client.get("/?variant=Uno").text
    # several picked: the first counts; unknown types: the default
    assert "1 games in 1 sessions" in client.get("/?variant=Bruno&variant=Uno").text
    assert "3 games in 2 sessions" in client.get("/?variant=nope").text


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
    # the default type needs no parameter
    assert 'href="/player/bob"' in client.get("/players").text


def test_player_and_charts_filtered(client, bruno):
    html = client.get("/player/cy-young").text
    assert "3 games in 2 sessions" in html
    assert 'data-src="/player/cy-young/charts.json"' in html
    data = client.get("/player/cy-young/charts.json").get_json()
    assert data["moving"]["x"] == [1, 2, 3]


def test_compare_filtered(client, bruno):
    html = client.get("/compare/bob/cy-young?variant=Bruno").text
    assert "The 1 games together" in html
    assert "/compare.json/bob/cy-young?variant=Bruno" in html


def test_filter_form(client):
    html = client.get("/sessions").text
    assert '<details class="variant-filter" >' in html
    assert "Game type: Uno default" in html
    assert html.count('name="variant"') == 2
    assert html.count("checked") == 1
    html = client.get("/sessions?variant=Bruno&sort=games").text
    assert '<details class="variant-filter" open>' in html
    assert "Game type: Black Rock Uno" in html
    assert '<input type="hidden" name="sort" value="games">' in html
    assert "variant-filter" not in client.get("/variants").text
