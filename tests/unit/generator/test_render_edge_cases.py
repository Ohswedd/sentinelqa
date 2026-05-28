"""Edge cases for the renderer filters and page-object helpers."""

from __future__ import annotations

import pytest
from engine.generator.page_objects import _capitalize_segment, route_to_page_name
from engine.generator.render import (
    RenderError,
    _js_string_filter,
    _regex_literal_filter,
    _regex_pattern_filter,
)
from jinja2 import Undefined


def test_js_string_filter_rejects_undefined() -> None:
    with pytest.raises(RenderError):
        _js_string_filter(Undefined())


def test_regex_literal_rejects_undefined() -> None:
    with pytest.raises(RenderError):
        _regex_literal_filter(Undefined())


def test_regex_pattern_rejects_undefined() -> None:
    with pytest.raises(RenderError):
        _regex_pattern_filter(Undefined())


def test_capitalize_segment_handles_camel_case() -> None:
    assert _capitalize_segment("maxLength") == "MaxLength"
    assert _capitalize_segment("XMLHttpRequest") == "XMLHttpRequest"


def test_route_to_page_name_handles_leading_digit() -> None:
    name = route_to_page_name("/2fa")
    assert name.startswith("Page") or name[0].isalpha()


def test_route_to_page_name_handles_punctuation() -> None:
    assert route_to_page_name("/user-settings") == "UserSettingsPage"
    assert route_to_page_name("/users/[id]") == "UsersIdPage"
