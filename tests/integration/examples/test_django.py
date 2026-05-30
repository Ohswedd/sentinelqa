"""Structural smoke for the Django example (Phase 26.03)."""

from __future__ import annotations

from .conftest import EXAMPLES, load_example_config, read_text


def test_django_layout_present() -> None:
    root = EXAMPLES / "django"
    for marker in (
        "manage.py",
        "requirements.txt",
        "README.md",
        "demo_site/__init__.py",
        "demo_site/settings.py",
        "demo_site/urls.py",
        "demo_site/wsgi.py",
        "core/__init__.py",
        "core/apps.py",
        "core/admin.py",
        "core/forms.py",
        "core/models.py",
        "core/urls.py",
        "core/views.py",
        "core/migrations/0001_initial.py",
        "templates/base.html",
        "templates/home.html",
        "templates/login.html",
        "templates/projects/list.html",
        "templates/projects/delete.html",
    ):
        assert (root / marker).is_file(), marker


def test_django_config_loads() -> None:
    cfg = load_example_config("django")
    assert cfg.project.framework == "django"
    assert str(cfg.target.base_url).startswith("http://127.0.0.1:8001")


def test_django_settings_have_security_hardening() -> None:
    settings = read_text("django", "demo_site", "settings.py")
    # The README claims these hardening defaults; assert them so doc drift fails.
    for marker in (
        "SECURE_CONTENT_TYPE_NOSNIFF = True",
        'X_FRAME_OPTIONS = "DENY"',
        "SESSION_COOKIE_HTTPONLY = True",
        'SESSION_COOKIE_SAMESITE = "Lax"',
        "CSRF_COOKIE_HTTPONLY = True",
    ):
        assert marker in settings, marker


def test_django_urls_expose_admin_and_auth() -> None:
    urls = read_text("django", "demo_site", "urls.py")
    assert '"admin/"' in urls
    assert '"login/"' in urls
    assert '"projects/"' in urls
