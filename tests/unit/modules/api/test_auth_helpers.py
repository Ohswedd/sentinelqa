"""Coverage for the auth helper functions (path templating)."""

from __future__ import annotations

from modules.api.checks.auth import _materialise
from modules.api.openapi import OpenApiOperation


def _op_with_params(parameters: tuple) -> OpenApiOperation:
    return OpenApiOperation(
        method="get",
        path="/items/{id}",
        operation_id="get",
        request_body_required=False,
        request_body_schema=None,
        request_body_content_type=None,
        response_schemas={200: {"type": "object"}},
        response_content_type={200: "application/json"},
        security_required=True,
        parameters=parameters,
    )


def test_materialise_integer_param() -> None:
    op = _op_with_params(({"name": "id", "in": "path", "schema": {"type": "integer"}},))
    assert _materialise(op) == "/items/1"


def test_materialise_string_param() -> None:
    op = _op_with_params(({"name": "id", "in": "path", "schema": {"type": "string"}},))
    assert _materialise(op) == "/items/sample"


def test_materialise_skips_non_path_param() -> None:
    op = _op_with_params(({"name": "filter", "in": "query", "schema": {"type": "string"}},))
    # No substitution because parameter is in query, not path.
    assert _materialise(op) == "/items/{id}"


def test_materialise_skips_param_with_missing_name() -> None:
    op = _op_with_params(({"in": "path", "schema": {"type": "string"}},))
    assert _materialise(op) == "/items/{id}"


def test_materialise_handles_param_without_schema() -> None:
    op = _op_with_params(({"name": "id", "in": "path"},))
    assert _materialise(op) == "/items/sample"
