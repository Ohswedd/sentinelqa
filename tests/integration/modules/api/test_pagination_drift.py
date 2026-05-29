"""Coverage for pagination drift branches (content-type / envelope)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig
from pytest_httpserver import HTTPServer

from modules.api.checks.pagination import run_pagination_check
from modules.api.openapi import load_openapi


def _paginated_spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer"}}],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"type": "array"}}},
                        }
                    },
                }
            }
        },
    }


@pytest.fixture
def api_config() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(pagination_max_pages=3),
    )


def test_content_type_drift_flags_finding(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_paginated_spec()), encoding="utf-8")
    # Page 1: JSON; page 2: text/plain.
    httpserver.expect_ordered_request("/items", method="GET").respond_with_json(
        [{"x": 1}], status=200
    )
    httpserver.expect_ordered_request("/items", method="GET").respond_with_data(
        "plain", status=200, content_type="text/plain"
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_pagination_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "PAGINATION-CONTENT-TYPE-DRIFT" for issue in result.issues)


def test_envelope_drift_flags_finding(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_paginated_spec()), encoding="utf-8")
    # Page 1: list; page 2: dict.
    httpserver.expect_ordered_request("/items", method="GET").respond_with_json(
        [{"x": 1}], status=200
    )
    httpserver.expect_ordered_request("/items", method="GET").respond_with_json(
        {"data": [{"y": 2}]}, status=200
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_pagination_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "PAGINATION-ENVELOPE-DRIFT" for issue in result.issues)


def test_pagination_non_json_response_returns_silently(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_paginated_spec()), encoding="utf-8")
    httpserver.expect_request("/items", method="GET").respond_with_data(
        "plain", status=200, content_type="text/plain"
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_pagination_check(client=client, doc=doc, config=api_config)
    # Plain text on page 1 → walker returns without raising findings.
    assert result.issues == ()


def test_pagination_invalid_json_returns_silently(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_paginated_spec()), encoding="utf-8")
    httpserver.expect_request("/items", method="GET").respond_with_data(
        "{not json", status=200, content_type="application/json"
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_pagination_check(client=client, doc=doc, config=api_config)
    assert result.issues == ()
