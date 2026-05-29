"""Unit coverage for :mod:`modules.api.checks.negative` helpers."""

from __future__ import annotations

from typing import Any

from modules.api.checks.negative import _build_valid_payload, _generate_variants, _sample_value
from modules.api.openapi import OpenApiOperation


def _op(request_body_schema: dict[str, Any]) -> OpenApiOperation:
    return OpenApiOperation(
        method="post",
        path="/users",
        operation_id="create",
        request_body_required=True,
        request_body_schema=request_body_schema,
        request_body_content_type="application/json",
        response_schemas={201: {"type": "object"}},
        response_content_type={201: "application/json"},
        security_required=False,
        parameters=(),
    )


def test_sample_value_returns_default_when_present() -> None:
    assert _sample_value({"default": 42, "type": "integer"}) == 42


def test_sample_value_returns_example_when_no_default() -> None:
    assert _sample_value({"example": "abc", "type": "string"}) == "abc"


def test_sample_value_returns_enum_first() -> None:
    assert _sample_value({"enum": ["a", "b"], "type": "string"}) == "a"


def test_sample_value_handles_each_primitive_type() -> None:
    assert _sample_value({"type": "integer"}) == 1
    assert _sample_value({"type": "number"}) == 1.0
    assert _sample_value({"type": "boolean"}) is False
    assert _sample_value({"type": "array"}) == []
    assert _sample_value({"type": "object"}) == {}
    assert _sample_value({"type": "string"}) == "sample"


def test_sample_value_minimum_for_numeric() -> None:
    assert _sample_value({"type": "integer", "minimum": 10}) == 10


def test_build_valid_payload_covers_every_property() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "admin": {"type": "boolean"},
        },
    }
    payload = _build_valid_payload(schema)
    assert set(payload.keys()) == {"name", "age", "admin"}


def test_build_valid_payload_returns_empty_for_non_object() -> None:
    assert _build_valid_payload({}) == {}


def test_generate_variants_includes_missing_required_when_required_listed() -> None:
    op = _op(
        {
            "type": "object",
            "required": ["email"],
            "properties": {"email": {"type": "string"}, "age": {"type": "integer"}},
        }
    )
    variants = _generate_variants(op, payload_cap_kb=16, max_variants=4)
    labels = [label for label, _ in variants]
    assert "missing_required" in labels


def test_generate_variants_includes_wrong_type_variant_for_integer() -> None:
    op = _op(
        {
            "type": "object",
            "properties": {"age": {"type": "integer", "maximum": 120}},
        }
    )
    variants = _generate_variants(op, payload_cap_kb=16, max_variants=4)
    labels = [label for label, _ in variants]
    assert "wrong_type" in labels


def test_generate_variants_clamps_to_max_variants() -> None:
    op = _op(
        {
            "type": "object",
            "required": ["email", "age"],
            "properties": {
                "email": {"type": "string"},
                "age": {"type": "integer", "maximum": 120},
                "is_admin": {"type": "boolean"},
            },
        }
    )
    variants = _generate_variants(op, payload_cap_kb=16, max_variants=2)
    assert len(variants) <= 2


def test_generate_variants_oversized_string_within_cap() -> None:
    op = _op(
        {
            "type": "object",
            "properties": {"note": {"type": "string"}},
        }
    )
    variants = _generate_variants(op, payload_cap_kb=2, max_variants=4)
    oversized = next((p for label, p in variants if label == "oversized_string"), None)
    assert oversized is not None
    note = oversized["note"]
    assert isinstance(note, str)
    # Must be ≤ (cap_kb - 1) KB.
    assert len(note) <= 1 * 1024


def test_generate_variants_boolean_field_wrong_type() -> None:
    op = _op(
        {
            "type": "object",
            "properties": {"flag": {"type": "boolean"}},
        }
    )
    variants = _generate_variants(op, payload_cap_kb=16, max_variants=4)
    wrong_type = next((p for label, p in variants if label == "wrong_type"), None)
    assert wrong_type is not None
    assert wrong_type["flag"] == "not_a_boolean"


def test_generate_variants_with_no_schema_returns_empty() -> None:
    op = OpenApiOperation(
        method="post",
        path="/x",
        operation_id="x",
        request_body_required=False,
        request_body_schema={},  # explicit empty (not None)
        request_body_content_type=None,
        response_schemas={},
        response_content_type={},
        security_required=False,
        parameters=(),
    )
    variants = _generate_variants(op, payload_cap_kb=16, max_variants=4)
    assert variants == []
