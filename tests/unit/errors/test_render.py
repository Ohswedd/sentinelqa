"""Tests for the error renderer."""

from __future__ import annotations

import json

from engine.errors import ConfigSchemaError, UnknownHostError
from engine.errors.render import render_error


def test_human_mode_includes_suggested_fix() -> None:
    err = ConfigSchemaError(detail="missing target.base_url")
    rendered = render_error(err, mode="human")
    assert "Suggested fix:" in rendered
    assert "E-CFG-002" in rendered


def test_human_mode_color_marker() -> None:
    err = UnknownHostError(host="evil.example.com")
    rendered_color = render_error(err, mode="human", color=True)
    assert "\033[1;31m" in rendered_color
    rendered_plain = render_error(err, mode="human", color=False)
    assert "\033[" not in rendered_plain


def test_json_mode_parses_back() -> None:
    err = UnknownHostError(host="evil.example.com")
    rendered = render_error(err, mode="json")
    payload = json.loads(rendered)
    assert payload["code"] == "E-SAFE-001"
    assert payload["exit_code"] == 4
    # JSON output is single-line, no ANSI.
    assert "\n" not in rendered
    assert "\033[" not in rendered
