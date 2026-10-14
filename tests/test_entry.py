import json
import re

import pytest
from werkzeug.datastructures import MultiDict

from unodb.db import WINNER, get_db

CSRF = "test-token"


def make_user(app, name, role):
    with app.app_context():
        return (
            get_db()
            .execute(
                "INSERT INTO users (name, role, webauthn_id) VALUES (?, ?, ?)",
                (name, role, name.encode()),
            )
            .lastrowid
        )


def as_user(client, uid):
    with client.session_transaction() as session:
        session["user_id"] = uid
        session["csrf"] = CSRF


def post(client, url, data=None):
    return client.post(url, data={"csrf": CSRF, **(data or {})})


def db_rows(app, sql, params=()):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql, params).fetchall()]


@pytest.fixture
def admin(app, client):
    uid = make_user(app, "Arun", "admin")
    as_user(client, uid)
    return uid


@pytest.fixture
def contributor(app, client):
    uid = make_user(app, "Joe Miller", "contributor")
    as_user(client, uid)
    return uid


def new_session(client, players, location="Berkeley", create=True, variant="1"):
    data = {"date": "2026-10-14", "location": location, "variant": variant}
    if create:
        data["create"] = "yes"
    return client.post(
        "/admin/sessions/new",
        data=MultiDict(
            [("csrf", CSRF), *data.items(), *[("player", p) for p in players]]
        ),
    )


def session_id(response):
    return int(re.search(r"/admin/sessions/(\d+)$", response.location)[1])


# --- creating sessions -----------------------------------------------------------


def test_admin_creates_session_with_existing_players(app, client, admin):
    response = new_session(client, ["Ann", "Bob", "Cy Young"], create=False)
    assert response.status_code == 303
    sid = session_id(response)
    seats = db_rows(
        app,
        "SELECT player, seat FROM session_players WHERE session = ? ORDER BY seat",
        (sid,),
    )
    assert [s["player"] for s in seats] == [1, 2, 3]
    row = db_rows(app, "SELECT * FROM session WHERE id = ?", (sid,))[0]
    assert row["created_by"] == admin
    assert row["number_of_players"] == 3


def test_new_players_need_confirmation(app, client, contributor):
    html = new_session(
        client, ["Ann Lee", "Bo Diddley"], "My Kitchen", create=False
    ).text
    assert "These don't exist yet and will be created" in html
    assert "player &#39;Ann Lee&#39;" in html
    assert "location &#39;My Kitchen&#39;" in html
    assert db_rows(app, "SELECT * FROM players WHERE name = 'Ann Lee'") == []

    response = new_session(client, ["Ann Lee", "Bo Diddley"], "My Kitchen")
    assert response.status_code == 303
    created = db_rows(app, "SELECT name, created_by FROM players WHERE id > 3")
    assert created == [
        {"name": "Ann Lee", "created_by": contributor},
        {"name": "Bo Diddley", "created_by": contributor},
    ]


@pytest.mark.parametrize(
    ("players", "problem"),
    [
        (["Ann", "Bo Diddley"], "is a player of another group"),
        (["Zed", "Bo Diddley"], "please use first and last name"),
        (["Bo Diddley", "bo diddley"], "in the list twice"),
        (["Bo Diddley"], "at least two players"),
        (["cy young", "Bo Diddley"], "is a player of another group"),
    ],
)
def test_contributor_player_names(app, client, contributor, players, problem):
    html = new_session(client, players).text
    assert problem in html
    assert (
        db_rows(app, "SELECT * FROM session WHERE created_by = ?", (contributor,)) == []
    )


def test_admin_may_use_single_names(client, admin):
    assert new_session(client, ["Zed", "Ann"]).status_code == 303


def test_names_clashing_in_the_url_are_taken(app, client, admin):
    # "Cy-Young" would get the same address as "Cy Young": /player/cy-young
    html = new_session(client, ["Cy-Young", "Ann"]).text
    assert "already taken (by &#39;Cy Young&#39;)" in html


def test_contributor_picks_own_players_again(app, client, contributor):
    new_session(client, ["Ann Lee", "Bo Diddley"])
    assert (
        new_session(client, ["Ann Lee", "Bo Diddley"], create=False).status_code == 303
    )


# --- games -----------------------------------------------------------------------


@pytest.fixture
def own_session(client, contributor):
    return session_id(new_session(client, ["Ann Lee", "Bo Diddley", "Cy Twombly"]))


def player_ids(app, sid):
    return [
        r["player"]
        for r in db_rows(
            app,
            "SELECT player FROM session_players WHERE session = ? ORDER BY seat",
            (sid,),
        )
    ]


def test_add_game(app, client, own_session):
    a, b, c = player_ids(app, own_session)
    response = post(
        client,
        f"/admin/sessions/{own_session}/games",
        {"winner": a, f"score-{b}": "12", f"score-{c}": "", "black": "yes"},
    )
    assert response.status_code == 303
    scores = db_rows(
        app, "SELECT player, score, position FROM scores ORDER BY id DESC LIMIT 2"
    )
    assert sorted((s["player"], s["score"], s["position"]) for s in scores) == [
        (a, WINNER, 0),
        (b, 12, 1),
    ]  # Cy didn't play this game
    game = db_rows(app, "SELECT * FROM games ORDER BY id DESC LIMIT 1")[0]
    assert game["end_with_black_card"] == 1
    # counts in the public statistics right away
    assert "5 games in 4 sessions" in client.get("/").text


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ({}, "Please mark who won."),
        ({"score-B": "x"}, "points must be a number"),
        ({"score-B": "1001"}, "points must be a number"),
        ({"score-B": "", "score-C": ""}, "at least two players"),
    ],
)
def test_game_problems(app, client, own_session, data, problem):
    a, b, c = player_ids(app, own_session)
    form = {"score-B": "5", "score-C": "7", **data}
    form = {k.replace("B", str(b)).replace("C", str(c)): v for k, v in form.items()}
    if data:
        form["winner"] = a
    if not data:
        form = {f"score-{b}": "5"}
    html = post(client, f"/admin/sessions/{own_session}/games", form).text
    assert problem in html
    assert db_rows(app, "SELECT * FROM games WHERE session = ?", (own_session,)) == []


def test_change_and_delete_game(app, client, own_session):
    a, b, c = player_ids(app, own_session)
    post(
        client,
        f"/admin/sessions/{own_session}/games",
        {"winner": a, f"score-{b}": "12"},
    )
    game = db_rows(app, "SELECT id FROM games WHERE session = ?", (own_session,))[0][
        "id"
    ]
    html = client.get(f"/admin/sessions/{own_session}?edit={game}").text
    assert "Change game 1" in html

    url = f"/admin/sessions/{own_session}/games/{game}"
    post(client, url, {"winner": b, f"score-{a}": "3", f"score-{c}": "8"})
    scores = {
        r["player"]: r["score"]
        for r in db_rows(
            app, "SELECT player, score FROM scores WHERE game = ?", (game,)
        )
    }
    assert scores == {a: 3, b: WINNER, c: 8}

    post(client, url + "/delete")
    assert db_rows(app, "SELECT * FROM games WHERE id = ?", (game,)) == []
    log = db_rows(
        app, "SELECT action, details FROM audit_log WHERE action LIKE 'game%'"
    )
    assert [entry["action"] for entry in log] == [
        "game added",
        "game changed",
        "game deleted",
    ]
    assert json.loads(log[1]["details"])["before"]["scores"] == {
        str(a): WINNER,
        str(b): 12,
    }


def test_add_player_and_change_details(app, client, own_session):
    post(
        client,
        f"/admin/sessions/{own_session}/players",
        {"player": "Di Ver", "create": "yes"},
    )
    assert len(player_ids(app, own_session)) == 4
    row = db_rows(
        app, "SELECT number_of_players FROM session WHERE id = ?", (own_session,)
    )
    assert row[0]["number_of_players"] == 4

    post(
        client,
        f"/admin/sessions/{own_session}/details",
        {"date": "2026-10-13", "location": "Berkeley", "variant": "2"},
    )
    row = db_rows(
        app, "SELECT date, variation FROM session WHERE id = ?", (own_session,)
    )
    assert row[0] == {"date": "2026-10-13", "variation": 2}


def test_delete_session(app, client, own_session):
    a, b, _ = player_ids(app, own_session)
    post(
        client, f"/admin/sessions/{own_session}/games", {"winner": a, f"score-{b}": "9"}
    )
    post(client, f"/admin/sessions/{own_session}/delete")
    assert client.get(f"/admin/sessions/{own_session}").status_code == 404
    assert "4 games in 3 sessions" in client.get("/").text


# --- permissions -----------------------------------------------------------------


def test_contributor_cannot_touch_other_sessions(app, client, own_session):
    a, b, _ = player_ids(app, own_session)
    post(
        client, f"/admin/sessions/{own_session}/games", {"winner": a, f"score-{b}": "9"}
    )
    game = db_rows(app, "SELECT id FROM games WHERE session = ?", (own_session,))[0][
        "id"
    ]
    before = db_rows(app, "SELECT * FROM scores ORDER BY id")

    as_user(client, make_user(app, "Eve Other", "contributor"))
    base = f"/admin/sessions/{own_session}"
    assert client.get(base).status_code == 403
    for url, data in [
        (f"{base}/games", {"winner": a, f"score-{b}": "1"}),
        (f"{base}/games/{game}", {"winner": b, f"score-{a}": "1"}),
        (f"{base}/games/{game}/delete", {}),
        (
            f"{base}/details",
            {"date": "2000-01-01", "location": "Berkeley", "variant": "1"},
        ),
        (f"{base}/players", {"player": "Eve Other Two", "create": "yes"}),
        (f"{base}/delete", {}),
    ]:
        assert post(client, url, data).status_code == 403, url
    # old sessions (owned by nobody) are off limits too
    assert client.get("/admin/sessions/1").status_code == 403
    assert db_rows(app, "SELECT * FROM scores ORDER BY id") == before
    assert "Eve" not in client.get("/admin/sessions").text


def test_editor_may_change_any_session(app, client, own_session):
    as_user(client, make_user(app, "Ed Itor", "editor"))
    assert client.get(f"/admin/sessions/{own_session}").status_code == 200
    assert client.get("/admin/sessions/1").status_code == 200


def test_entry_needs_login_and_csrf(app, client, own_session):
    assert client.post(f"/admin/sessions/{own_session}/delete").status_code == 403
    with client.session_transaction() as session:
        session.clear()
    assert client.get("/admin/sessions/new").status_code == 302


# --- game types ------------------------------------------------------------------

RULES = "Stacking +2 and +4 is allowed; the game ends when one player is out."


def test_create_game_type(app, client, contributor):
    response = post(
        client,
        "/admin/variants/new",
        {"name": "Stacking Uno", "short": "stacking", "description": RULES},
    )
    assert response.location == "/variant/stacking"
    html = client.get("/variant/stacking").text
    assert "Stacking +2 and +4" in html
    assert "described by Joe Miller" in html
    assert "Stacking Uno" in client.get("/variants").text


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ({"description": "short"}, "Please describe the rules"),
        ({"short": "Uno"}, "already used"),
        ({"short": "has space"}, "letters, digits or"),
    ],
)
def test_game_type_problems(client, contributor, data, problem):
    form = {"name": "Stacking Uno", "short": "stacking", "description": RULES, **data}
    assert problem in post(client, "/admin/variants/new", form).text


def test_game_type_permissions(app, client, contributor):
    post(
        client,
        "/admin/variants/new",
        {"name": "Mine", "short": "mine", "description": RULES},
    )
    vid = db_rows(app, "SELECT id FROM variations WHERE short = 'mine'")[0]["id"]
    assert client.get(f"/admin/variants/{vid}").status_code == 200
    assert client.get("/admin/variants/1").status_code == 403  # not theirs
    as_user(client, make_user(app, "Eve Other", "contributor"))
    assert client.get(f"/admin/variants/{vid}").status_code == 403
    as_user(client, make_user(app, "Admin Two", "admin"))
    assert client.get(f"/admin/variants/{vid}").status_code == 200


def test_default_game_type(app, client, contributor):
    post(client, "/admin/settings", {"default_variant": "2"})
    html = client.get("/admin/sessions/new").text
    assert re.search(r'<option value="2" selected>', html)
