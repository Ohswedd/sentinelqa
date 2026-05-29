"""Edge-case coverage for :mod:`modules.api.openapi` parsers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.api.openapi import (
    _extract_operations,
    _field_types,
    _resolve_refs,
    load_openapi,
)


def _spec(paths: Any) -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": paths,
    }


def test_extract_operations_skips_non_dict_path_item() -> None:
    out = _extract_operations(_spec({"/items": "string-not-dict"}))
    assert out == []


def test_extract_operations_skips_non_dict_operation_object() -> None:
    out = _extract_operations(_spec({"/items": {"get": "not-a-dict"}}))
    assert out == []


def test_extract_operations_handles_missing_request_body_content() -> None:
    spec = _spec(
        {
            "/items": {
                "post": {
                    "operationId": "create",
                    "requestBody": {"required": True},
                    "responses": {"200": {"description": "ok"}},
                }
            }
        }
    )
    out = _extract_operations(spec)
    assert len(out) == 1
    assert out[0].request_body_schema is None


def test_extract_operations_skips_unparseable_status_codes() -> None:
    spec = _spec(
        {
            "/items": {
                "get": {
                    "operationId": "list",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        },
                        "weird": {"description": "??"},
                    },
                }
            }
        }
    )
    out = _extract_operations(spec)
    assert 200 in out[0].response_schemas
    # 'weird' key was skipped silently.
    assert all(isinstance(s, int) for s in out[0].response_schemas)


def test_extract_operations_handles_non_dict_parameter_entry() -> None:
    spec = _spec(
        {
            "/items": {
                "get": {
                    "operationId": "list",
                    "parameters": ["not-a-dict", {"name": "page", "in": "query"}],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        }
    )
    out = _extract_operations(spec)
    assert len(out[0].parameters) == 1


def test_extract_operations_handles_missing_content_type_in_response() -> None:
    spec = _spec(
        {
            "/items": {
                "get": {
                    "operationId": "list",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": "not-a-dict",  # silently skipped
                        }
                    },
                }
            }
        }
    )
    out = _extract_operations(spec)
    assert out[0].response_schemas == {}


def test_resolve_refs_returns_schema_when_no_ref() -> None:
    spec = {"components": {"schemas": {"X": {"type": "string"}}}}
    schema = {"type": "integer"}
    assert _resolve_refs(schema, spec) is schema


def test_resolve_refs_returns_unmodified_when_ref_target_missing() -> None:
    spec: dict[str, Any] = {"components": {"schemas": {}}}
    schema = {"$ref": "#/components/schemas/Missing"}
    assert _resolve_refs(schema, spec) == schema


def test_resolve_refs_returns_unmodified_when_ref_not_local() -> None:
    schema = {"$ref": "https://example.com/x.json"}
    assert _resolve_refs(schema, {}) == schema


def test_load_openapi_collects_each_server_url(tmp_path: Path) -> None:
    spec = _spec(
        {"/items": {"get": {"operationId": "list", "responses": {"200": {"description": "ok"}}}}}
    )
    spec["servers"] = [{"url": "https://api"}, {"url": "https://staging"}]
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    doc = load_openapi(path)
    assert doc.base_paths == ("https://api", "https://staging")


def test_load_openapi_with_paths_value_not_dict(tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {},  # empty
    }
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    doc = load_openapi(path)
    assert doc.operations == ()


def test_field_types_handle_list_typed_schema() -> None:
    """OpenAPI 3.1 allows `type: [string, null]`; we record the first entry."""

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": ["string", "null"]},
            "age": {"type": "integer"},
            "no_type": {"description": "skipped"},
        },
    }
    result = dict(_field_types(schema))
    assert result["name"] == "string"
    assert result["age"] == "integer"
    assert "no_type" not in result


def test_field_types_handles_non_dict_properties() -> None:
    schema = {"properties": "not-a-dict"}
    assert _field_types(schema) == []


def test_field_types_handles_empty_type_list() -> None:
    schema = {"type": "object", "properties": {"x": {"type": []}}}
    assert _field_types(schema) == []
