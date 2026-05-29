"""Unit coverage for :mod:`modules.api.openapi`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.api.openapi import (
    OpenApiDocument,
    OpenApiOperation,
    load_openapi,
)


def _spec_with_refs() -> dict[str, object]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "components": {
            "schemas": {
                "Item": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                }
            }
        },
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Item"}
                                }
                            },
                        },
                        "default": {
                            "description": "error",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"error": {"type": "string"}},
                                    }
                                }
                            },
                        },
                    },
                },
                "post": {
                    "operationId": "create_item",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Item"}}
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Item"}
                                }
                            },
                        }
                    },
                },
            }
        },
        "servers": [{"url": "https://api.example.com/v1"}],
    }


def test_load_openapi_json(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(_spec_with_refs()), encoding="utf-8")
    doc = load_openapi(path)
    assert isinstance(doc, OpenApiDocument)
    assert len(doc.operations) == 2
    assert doc.base_paths == ("https://api.example.com/v1",)


def test_load_openapi_yaml(tmp_path: Path) -> None:
    import yaml as _yaml

    path = tmp_path / "openapi.yaml"
    path.write_text(_yaml.dump(_spec_with_refs()), encoding="utf-8")
    doc = load_openapi(path)
    assert len(doc.operations) == 2


def test_load_openapi_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_openapi(path)


def test_load_openapi_rejects_invalid_spec(tmp_path: Path) -> None:
    from openapi_spec_validator.exceptions import OpenAPIError

    path = tmp_path / "bad.json"
    # Missing required openapi/info fields → openapi-spec-validator
    # raises a subclass of OpenAPIError (either ValidatorDetectError
    # or OpenAPIValidationError, depending on which discovery step
    # fails first). Either way the spec is unloadable.
    path.write_text('{"paths":{}}', encoding="utf-8")
    with pytest.raises(OpenAPIError):
        load_openapi(path)


def test_resolves_refs_in_request_and_response_schemas(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(_spec_with_refs()), encoding="utf-8")
    doc = load_openapi(path)
    post_op = next(op for op in doc.operations if op.method == "post")
    assert post_op.request_body_required is True
    assert post_op.request_body_schema is not None
    assert "id" in post_op.request_body_schema.get("required", [])
    assert post_op.request_body_content_type == "application/json"


def test_default_response_indexed_as_status_zero(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(_spec_with_refs()), encoding="utf-8")
    doc = load_openapi(path)
    get_op = next(op for op in doc.operations if op.method == "get")
    assert 200 in get_op.response_schemas
    assert 0 in get_op.response_schemas


def test_snapshot_endpoints_emits_sorted_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(_spec_with_refs()), encoding="utf-8")
    doc = load_openapi(path)
    snapshot = doc.snapshot_endpoints()
    # POST /items snapshot should report required request field 'id'.
    post_snap = next(e for e in snapshot if e.method == "POST" and e.path == "/items")
    assert "id" in post_snap.required_request_fields
    # GET /items snapshot should include 200:id as a required response field.
    get_snap = next(e for e in snapshot if e.method == "GET" and e.path == "/items")
    assert "200:id" in get_snap.required_response_fields


def test_authenticated_operations_filters_correctly(tmp_path: Path) -> None:
    spec = _spec_with_refs()
    spec["security"] = [{"bearer": []}]
    spec["components"]["securitySchemes"] = {  # type: ignore[index]
        "bearer": {"type": "http", "scheme": "bearer"}
    }
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    doc = load_openapi(path)
    auth_ops = doc.authenticated_operations()
    assert len(auth_ops) == len(doc.operations)


def test_parameters_extracted_for_path_template(tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/items/{id}": {
                "get": {
                    "operationId": "get_item",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    doc = load_openapi(path)
    op = doc.operations[0]
    assert isinstance(op, OpenApiOperation)
    assert len(op.parameters) == 1
    assert op.parameters[0]["name"] == "id"


def test_global_security_inherited_when_operation_security_unset(tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
        "security": [{"bearer": []}],
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    doc = load_openapi(path)
    assert doc.operations[0].security_required is True
