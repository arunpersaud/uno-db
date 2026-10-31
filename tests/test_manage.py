"""Admin-only pages, and the access rules of every admin route."""

import pytest
from test_entry import CSRF, as_user, db_rows, make_user, post

# routes that work without a login (passkey ceremonies and the invite page);
# a new public route has to be added here on purpose
PUBLIC = {
    "admin.login",
    "admin.invite",
    "admin.logout",
    "admin.register_options",
    "admin.register_verify",
    "admin.login_options",
    "admin.login_verify",
}
# only for role admin
ADMIN_ONLY = {
    "admin.users",
    "admin.set_role",
    "admin.people",
    "admin.rename_player",
    "admin.rename_location",
    "admin.audit_log",
}


def admin_rules(app):
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("admin."):
            args = {a: (1 if a.endswith("_id") else "x") for a in rule.arguments}
            for method in rule.methods & {"GET", "POST"}:
                yield (
                    rule.endpoint,
                    method,
                    app.url_map.bind("localhost").build(
                        rule.endpoint, args, method=method
                    ),
                )


def call(client, method, url):
    if method == "POST":
        return client.post(url, data={"csrf": CSRF})
    return client.get(url)


def test_every_admin_route_needs_login(app):
    seen = set()
    for endpoint, method, url in admin_rules(app):
        seen.add(endpoint)
        if endpoint in PUBLIC:
            continue
        client = app.test_client()
        with client.session_transaction() as session:
            session["csrf"] = CSRF  # a visitor with a session, not logged in
        response = call(client, method, url)
        assert response.status_code == 302, (endpoint, method, response.status_code)
        assert response.location.endswith("/admin/login"), (endpoint, method)
    assert seen >= ADMIN_ONLY and seen >= PUBLIC


@pytest.mark.parametrize("role", ["editor", "contributor"])
def test_admin_pages_refuse_other_roles(app, role):
    uid = make_user(app, "Someone", role)
    client = app.test_client()
    as_user(client, uid)
    checked = 0
    for endpoint, method, url in admin_rules(app):
        if endpoint in ADMIN_ONLY:
            assert call(client, method, url).status_code == 403, (endpoint, method)
            checked += 1
    assert checked == len(ADMIN_ONLY)


def test_disabled_user_is_logged_out(app, client):
    uid = make_user(app, "Gone", "admin")
    as_user(client, uid)
    assert client.get("/admin/users").status_code == 200
    with app.app_context():
        from unodb.db import get_db

        get_db().execute(
            "UPDATE users SET disabled = '2026-10-31' WHERE id = ?", (uid,)
        )
    assert client.get("/admin/users").status_code == 302


def test_demoted_user_loses_admin_pages_at_once(app, client):
    uid = make_user(app, "Arun", "admin")
    as_user(client, uid)
    assert client.get("/admin/audit").status_code == 200
    with app.app_context():
        from unodb.db import get_db

        get_db().execute("UPDATE users SET role = 'editor' WHERE id = ?", (uid,))
    assert client.get("/admin/audit").status_code == 403


# --- roles ---------------------------------------------------------------


@pytest.fixture
def boss(app, client):
    uid = make_user(app, "Arun", "admin")
    as_user(client, uid)
    return uid


def role_of(app, uid):
    return db_rows(app, "SELECT role FROM users WHERE id = ?", (uid,))[0]["role"]


def test_admin_sets_editor_and_contributor(app, client, boss):
    uid = make_user(app, "Joe Miller", "contributor")
    assert "Joe Miller" in client.get("/admin/users").text
    assert (
        post(client, f"/admin/users/{uid}/role", {"role": "editor"}).status_code == 303
    )
    assert role_of(app, uid) == "editor"
    post(client, f"/admin/users/{uid}/role", {"role": "contributor"})
    assert role_of(app, uid) == "contributor"
    log = db_rows(app, "SELECT user_id, action, details FROM audit_log ORDER BY id")
    assert [e["action"] for e in log] == ["role changed", "role changed"]
    assert log[0]["user_id"] == boss and '"after": "editor"' in log[0]["details"]


def test_admin_rights_are_command_line_only(app, client, boss):
    joe = make_user(app, "Joe Miller", "contributor")
    other = make_user(app, "Other Admin", "admin")
    assert (
        post(client, f"/admin/users/{joe}/role", {"role": "admin"}).status_code == 403
    )
    assert role_of(app, joe) == "contributor"
    # an admin can't be changed here, not even to editor, not even yourself
    for target in (other, boss):
        assert (
            post(client, f"/admin/users/{target}/role", {"role": "editor"}).status_code
            == 403
        )
        assert role_of(app, target) == "admin"
    assert post(client, f"/admin/users/{joe}/role", {"role": "root"}).status_code == 400
    assert post(client, "/admin/users/999/role", {"role": "editor"}).status_code == 404
    assert db_rows(app, "SELECT * FROM audit_log") == []
    # the page offers no way to pick admin
    html = client.get("/admin/users").text
    assert '<option value="admin"' not in html


# --- renaming ---------------------------------------------------------------


def test_rename_player_and_location(app, client, boss):
    assert (
        post(client, "/admin/players/3/rename", {"name": "  Cy   Younger "}).status_code
        == 303
    )
    assert (
        db_rows(app, "SELECT name FROM players WHERE id = 3")[0]["name"] == "Cy Younger"
    )
    assert (
        post(client, "/admin/locations/2/rename", {"name": "Lodi, CA"}).status_code
        == 303
    )
    assert (
        db_rows(app, "SELECT name FROM locations WHERE id = 2")[0]["name"] == "Lodi, CA"
    )
    log = db_rows(app, "SELECT action, details FROM audit_log ORDER BY id")
    assert [e["action"] for e in log] == ["player renamed", "location renamed"]
    assert '"before": "Cy Young"' in log[0]["details"]
    assert "player/cy-younger" in client.get("/players").text


@pytest.mark.parametrize(
    ("url", "name", "problem"),
    [
        ("/admin/players/3/rename", "ann", "already taken"),
        ("/admin/players/3/rename", "BOB", "already taken"),
        ("/admin/players/3/rename", "A", "2 to 60"),
        ("/admin/players/3/rename", "", "2 to 60"),
        ("/admin/locations/2/rename", "berkeley", "already taken"),
    ],
)
def test_rename_problems(app, client, boss, url, name, problem):
    response = post(client, url, {"name": name})
    assert response.status_code == 400
    assert problem in response.text
    assert db_rows(app, "SELECT * FROM audit_log") == []


def test_rename_to_same_name_is_fine(app, client, boss):
    assert post(client, "/admin/players/1/rename", {"name": "Ann"}).status_code == 303
    assert (
        post(client, "/admin/players/1/rename", {"name": "ANN"}).status_code == 303
    )  # case change
    assert db_rows(app, "SELECT name FROM players WHERE id = 1")[0]["name"] == "ANN"


def test_rename_unknown_item(client, boss):
    assert post(client, "/admin/players/99/rename", {"name": "Zed"}).status_code == 404


# --- audit log ---------------------------------------------------------------


def test_audit_log_page(app, client, boss):
    post(client, "/admin/players/3/rename", {"name": "Cy Younger"})
    post(client, "/admin/locations/2/rename", {"name": "Lodi, CA"})
    html = client.get("/admin/audit").text
    assert "player renamed" in html and "Cy Younger" in html and "Arun" in html
    only = client.get("/admin/audit?action=location+renamed").text
    assert "location renamed" in only and "<td>player renamed</td>" not in only
    assert client.get("/admin/audit?page=5").status_code == 200
