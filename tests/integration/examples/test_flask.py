"""Structural smoke for the Flask example (Phase 26.04)."""

from __future__ import annotations

from .conftest import EXAMPLES, load_example_config, read_text


def test_flask_layout_present() -> None:
    root = EXAMPLES / "flask"
    assert (root / "app.py").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "README.md").is_file()
    for tpl in ("base.html", "home.html", "login.html", "projects.html"):
        assert (root / "templates" / tpl).is_file(), tpl


def test_flask_config_loads() -> None:
    cfg = load_example_config("flask")
    assert cfg.project.name == "sentinelqa-flask-example"
    assert cfg.project.framework == "flask"
    assert str(cfg.target.base_url).startswith("http://127.0.0.1:5001")
    assert cfg.policy.min_quality_score == 85


def test_flask_app_routes_are_exhaustive() -> None:
    src = read_text("flask", "app.py")
    # The README documents these exact routes; assert they all live in app.py
    # so doc drift can't sneak in.
    for marker in (
        '@app.get("/")',
        '@app.get("/login")',
        '@app.post("/login")',
        '@app.post("/logout")',
        '@app.get("/projects")',
        '@app.post("/projects")',
        '@app.post("/projects/<int:project_id>/delete")',
        '@app.get("/health")',
    ):
        assert marker in src, marker


def test_flask_readme_documents_demo_target() -> None:
    body = read_text("flask", "README.md")
    assert "make demo-flask" in body
    assert "sentinel audit" in body
