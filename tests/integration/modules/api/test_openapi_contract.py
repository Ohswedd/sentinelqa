"""OpenAPI contract check integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig
from pytest_httpserver import HTTPServer

from modules.api.checks.contract_openapi import run_openapi_contract_check
from modules.api.openapi import load_openapi


def _minimal_spec(*, response_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/items/{item_id}": {
                "get": {
                    "operationId": "get_item",
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": response_schema}},
                        }
                    },
                }
            }
        },
    }


@pytest.fixture
def api_config() -> RootConfig:
    return RootConfig(
        project={"name": "api-fixture", "framework": "unknown", "package_manager": "unknown"},
        target={
            "base_url": "http://127.0.0.1:1",
            "allowed_hosts": ("127.0.0.1",),
        },
        api=ApiConfig(),
    )


def test_compliant_endpoint_produces_no_issues(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    schema = {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
        },
    }
    spec = _minimal_spec(response_schema=schema)
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    httpserver.expect_request("/items/1", method="GET").respond_with_json(
        {"id": 1, "name": "alice"}, status=200
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_openapi_contract_check(client=client, doc=doc, config=api_config)
    assert result.check == "contract"
    assert result.targets_scanned == 1
    assert result.issues == ()


def test_missing_required_field_flags_schema_violation(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    schema = {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
        },
    }
    spec = _minimal_spec(response_schema=schema)
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    # Missing 'name' field — schema requires it.
    httpserver.expect_request("/items/1", method="GET").respond_with_json({"id": 1}, status=200)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_openapi_contract_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "CONTRACT-MISSING-FIELD" for issue in result.issues), [
        issue.model_dump() for issue in result.issues
    ]


def test_undocumented_status_flags_contract_status(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    schema = {
        "type": "object",
        "properties": {"id": {"type": "integer"}},
    }
    spec = _minimal_spec(response_schema=schema)
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    httpserver.expect_request("/items/1", method="GET").respond_with_data("boom", status=500)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_openapi_contract_check(client=client, doc=doc, config=api_config)
    assert any(
        issue.rule_id == "CONTRACT-STATUS" and issue.severity == "critical"
        for issue in result.issues
    )


def test_invalid_json_response_flags_invalid_json(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
    spec = _minimal_spec(response_schema=schema)
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    httpserver.expect_request("/items/1", method="GET").respond_with_data(
        "<html>not json</html>",
        status=200,
        content_type="application/json",
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_openapi_contract_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "CONTRACT-INVALID-JSON" for issue in result.issues)


def test_wrong_content_type_flags_content_type_issue(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
    spec = _minimal_spec(response_schema=schema)
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    httpserver.expect_request("/items/1", method="GET").respond_with_data(
        "plain", status=200, content_type="text/plain"
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_openapi_contract_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "CONTRACT-CONTENT-TYPE" for issue in result.issues)
