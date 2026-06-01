"""Tests for the template renderer."""

from __future__ import annotations

import pytest
from engine.generator.render import (
    GENERATOR_BANNER,
    GENERATOR_BANNER_MARKER,
    RenderError,
    render_template,
)


def test_renders_smoke_template_with_minimal_context() -> None:
    body = render_template(
        "smoke.spec.ts.j2",
        {
            "describe_title": "Smoke /",
            "test_title": "smoke /",
            "tags": ["@p0"],
            "route_path": "/",
            "anchor_role": "main",
            "anchor_name": "",
        },
    )
    assert GENERATOR_BANNER_MARKER in body
    assert body.startswith(GENERATOR_BANNER)
    assert "test.describe" in body
    assert "page.goto" in body
    # anchor name omitted should not emit `name:` arg
    assert "{ name:" not in body


def test_missing_variable_raises() -> None:
    with pytest.raises(RenderError) as exc:
        render_template(
            "smoke.spec.ts.j2",
            {"describe_title": "x"},  # most vars missing
        )
    assert "undefined" in str(exc.value).lower()


def test_unknown_template_raises() -> None:
    with pytest.raises(RenderError) as exc:
        render_template("does_not_exist.j2", {})
    assert "not found" in str(exc.value).lower()


def test_regex_literal_escapes_metachars() -> None:
    body = render_template(
        "smoke.spec.ts.j2",
        {
            "describe_title": "x",
            "test_title": "x",
            "tags": [],
            "route_path": "/api/v1/users",
            "anchor_role": "",
            "anchor_name": "",
        },
    )
    # `/api/v1/users` becomes `/\/api\/v1\/users/i` — the `/` are
    # escaped so the literal isn't terminated early.
    assert r"/\/api\/v1\/users/i" in body


def test_regex_pattern_preserves_alternation() -> None:
    body = render_template(
        "login.spec.ts.j2",
        {
            "tags": ["@p0"],
            "login_path": "/login",
            "email_env_name": "E",
            "password_env_name": "P",
            "email_label": "email",
            "password_label": "password",
            "submit_label": "sign in|log in",
            "success_url_regex": "dashboard|home",
            "validation_message_regex": "required|invalid",
            "post_login_role": "",
        },
    )
    # Pipes must survive (alternation), not be escaped.
    assert "/sign in|log in/i" in body
    assert "/dashboard|home/i" in body


def test_js_string_filter_escapes_quotes() -> None:
    body = render_template(
        "smoke.spec.ts.j2",
        {
            "describe_title": 'has "quotes"',
            "test_title": "x",
            "tags": [],
            "route_path": "/",
            "anchor_role": "",
            "anchor_name": "",
        },
    )
    assert r"has \"quotes\"" in body


def test_extra_templates_loader_overrides_filesystem() -> None:
    body = render_template(
        "smoke.spec.ts.j2",
        {},
        extra_templates={"smoke.spec.ts.j2": "{{ banner }}// override\n"},
    )
    assert "// override" in body
    # Banner injection still works.
    assert GENERATOR_BANNER_MARKER in body


def test_template_without_banner_marker_raises() -> None:
    with pytest.raises(RenderError) as exc:
        render_template(
            "bad.j2",
            {},
            extra_templates={"bad.j2": "// no banner here\n"},
        )
    assert "banner" in str(exc.value).lower()
