"""Shared fixtures for discovery integration tests.

Uses ``pytest-httpserver`` to spin up a tiny local app that exposes:

- ``/``         — landing page with an anchor to /dashboard and /login
- ``/dashboard``— requires auth: returns 401 anonymously, 200 with cookie
- ``/login``    — login form (POST /login → sets a cookie + redirects to /dashboard)
- ``/admin``    — anonymously returns 200 (UI-only auth smell), 200 with cookie
- ``/missing``  — returns 404
- ``/api/users``— returns 200 with a JSON list
- ``/api/items/123`` — returns 200 (used for path templating tests)
- ``/api/broken`` — returns 500 (5xx flag test)
- ``/openapi.json`` — minimal OpenAPI 3.0 doc
- ``/bundle.js`` — JS body referencing `/api/users`, `/api/items/{id}`, `/api/hidden`

The fixture is deliberately small so tests are deterministic and fast.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_httpserver import HTTPServer

LANDING_HTML = """\
<!doctype html>
<html lang="en">
<head><title>Test app</title></head>
<body>
  <header><h1>Welcome</h1></header>
  <nav>
    <a href="/dashboard">Dashboard</a>
    <a href="/login">Sign in</a>
    <a href="/admin">Admin</a>
    <a href="/missing">Missing route</a>
  </nav>
  <main>
    <button>Click me</button>
    <form action="/contact" method="post">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" required />
      <input type="submit" value="Send" />
    </form>
    <form action="/no-validation" method="post">
      <input name="freeform" type="text" />
      <input type="submit" value="Send" />
    </form>
    <form>
      <input name="orphan" type="text" />
      <input type="submit" value="Submit" />
    </form>
  </main>
  <script src="/bundle.js"></script>
</body>
</html>
"""

LOGIN_HTML = """\
<!doctype html>
<html><head><title>Sign in</title></head>
<body>
  <form action="/login" method="post">
    <label for="user">User</label>
    <input id="user" name="username" type="text" required />
    <label for="pw">Password</label>
    <input id="pw" name="password" type="password" required />
    <input type="submit" value="Sign in" />
  </form>
</body></html>
"""

DASHBOARD_AUTH_HTML = """\
<!doctype html>
<html><head><title>Dashboard</title></head>
<body>
  <h1>Dashboard</h1>
  <p>You are logged in.</p>
  <button aria-label="Open profile">Profile</button>
  <a href="/api/users">List users</a>
  <a href="/">Home</a>
</body></html>
"""

ADMIN_HTML = """\
<!doctype html>
<html><head><title>Admin</title></head>
<body>
  <h1>Admin</h1>
  <p>Public admin page.</p>
  <a href="/api/users">Users</a>
</body></html>
"""

OPENAPI_DOC = {
    "openapi": "3.0.3",
    "info": {"title": "Test API", "version": "1.2.3"},
    "paths": {
        "/api/users": {
            "get": {
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "array"}}},
                    }
                }
            }
        },
        "/api/items/{id}": {
            "get": {
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/api/orphan": {"get": {"responses": {"204": {"description": "no body"}}}},
    },
}

BUNDLE_JS = """\
const ROUTES = {
  users: '/api/users',
  items: '/api/items/[id]',
  hidden: '/api/hidden',
  static: '/static/main.css'
};
fetch(ROUTES.users).then(r => r.json());
"""


@pytest.fixture
def discovery_server(httpserver: HTTPServer) -> Iterator[HTTPServer]:
    httpserver.expect_request("/").respond_with_data(LANDING_HTML, content_type="text/html")
    httpserver.expect_request("/login", method="GET").respond_with_data(
        LOGIN_HTML, content_type="text/html"
    )
    httpserver.expect_request("/login", method="POST").respond_with_data(
        "ok",
        status=303,
        headers={"Set-Cookie": "session=valid; Path=/", "Location": "/dashboard"},
    )

    # /dashboard: anonymous → 401, authenticated (cookie) → 200.
    from werkzeug.wrappers import Response

    def dashboard_handler(request):  # type: ignore[no-untyped-def]
        cookie = request.headers.get("cookie", "")
        if "session=valid" in cookie:
            return Response(DASHBOARD_AUTH_HTML, status=200, content_type="text/html")
        return Response("", status=401, content_type="text/plain")

    httpserver.expect_request("/dashboard").respond_with_handler(dashboard_handler)
    httpserver.expect_request("/admin").respond_with_data(ADMIN_HTML, content_type="text/html")
    httpserver.expect_request("/missing").respond_with_data("not found", status=404)
    httpserver.expect_request("/api/users").respond_with_json([{"id": 1}, {"id": 2}])
    httpserver.expect_request("/api/items/123").respond_with_json({"id": 123})
    httpserver.expect_request("/api/broken").respond_with_data("oops", status=500)
    httpserver.expect_request("/openapi.json").respond_with_json(OPENAPI_DOC)
    httpserver.expect_request("/bundle.js").respond_with_data(
        BUNDLE_JS, content_type="application/javascript"
    )
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /\n", content_type="text/plain"
    )
    yield httpserver


@pytest.fixture
def discovery_base_url(discovery_server: HTTPServer) -> str:
    url: str = discovery_server.url_for("/")
    return url
