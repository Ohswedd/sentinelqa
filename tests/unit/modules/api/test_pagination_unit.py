"""Unit coverage for :mod:`modules.api.checks.pagination` helpers."""

from __future__ import annotations

from modules.api.checks.pagination import _envelope_shape, _is_empty_page


def test_envelope_shape_for_list() -> None:
    assert _envelope_shape([]) == "[]"
    assert _envelope_shape([1, 2]) == "[]"


def test_envelope_shape_for_dict_sorts_keys() -> None:
    assert _envelope_shape({"b": 1, "a": 2}) == "{a,b}"


def test_envelope_shape_for_other_types() -> None:
    assert _envelope_shape("string") == "str"
    assert _envelope_shape(42) == "int"


def test_is_empty_page_for_list() -> None:
    assert _is_empty_page([]) is True
    assert _is_empty_page([1]) is False


def test_is_empty_page_for_dict_with_data_key() -> None:
    assert _is_empty_page({"data": []}) is True
    assert _is_empty_page({"items": []}) is True
    assert _is_empty_page({"results": []}) is True
    assert _is_empty_page({"data": [1]}) is False


def test_is_empty_page_for_dict_without_known_keys() -> None:
    assert _is_empty_page({"other": []}) is False


def test_is_empty_page_for_other_types() -> None:
    assert _is_empty_page("nope") is False
    assert _is_empty_page(None) is False
