"""Tiny Flask example for SentinelQA Phase 26.

Provides cookie-based session auth plus an in-memory CRUD for the
"Project" entity. Deliberately small so it boots quickly and produces a
clean SentinelQA audit. Run with `make demo-flask` (see top-level
Makefile) — the app binds to 127.0.0.1:5001 by default.

Safety: the example is for local development. It is not intended to
host real user data; the secret key is rotated per-process and sessions
are signed but not encrypted.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from typing import Final

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

USERS: Final[dict[str, str]] = {
    # demo / demo — documented in README.md.
    "demo": "demo",
}


@dataclass
class Project:
    id: int
    name: str
    description: str
    owner: str = field(default="demo")


_PROJECTS: dict[int, Project] = {
    1: Project(id=1, name="SentinelQA", description="The release-confidence engine."),
    2: Project(id=2, name="Internal Docs", description="Docs site for the team."),
}
_NEXT_ID: list[int] = [3]


def _login_required(user: str | None) -> str:
    if not user:
        abort(401)
    return user


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SENTINEL_FLASK_SECRET", secrets.token_hex(32))
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Mark cookies Secure only when running behind HTTPS in production. For
    # the local demo we keep this off so the cookie is set on http://.
    app.config["SESSION_COOKIE_SECURE"] = False

    @app.after_request
    def _security_headers(resp: Response) -> Response:
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'",
        )
        return resp

    @app.get("/")
    def home() -> str:
        return render_template("home.html", user=session.get("user"))

    @app.get("/login")
    def login_get() -> str:
        return render_template("login.html")

    @app.post("/login")
    def login_post() -> Response:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if USERS.get(username) == password:
            session["user"] = username
            return redirect(url_for("projects_list"))
        flash("Invalid credentials")
        return redirect(url_for("login_get"))

    @app.post("/logout")
    def logout() -> Response:
        session.pop("user", None)
        return redirect(url_for("home"))

    @app.get("/projects")
    def projects_list() -> str:
        user = _login_required(session.get("user"))
        items = sorted(_PROJECTS.values(), key=lambda p: p.id)
        return render_template("projects.html", projects=items, user=user)

    @app.post("/projects")
    def projects_create() -> Response:
        _login_required(session.get("user"))
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Name is required")
            return redirect(url_for("projects_list"))
        new_id = _NEXT_ID[0]
        _NEXT_ID[0] += 1
        _PROJECTS[new_id] = Project(id=new_id, name=name, description=description)
        return redirect(url_for("projects_list"))

    @app.post("/projects/<int:project_id>/delete")
    def projects_delete(project_id: int) -> Response:
        _login_required(session.get("user"))
        _PROJECTS.pop(project_id, None)
        return redirect(url_for("projects_list"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=False)
