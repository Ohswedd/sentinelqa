"""Phase 22.07 — pagination + error-shape integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig
from pytest_httpserver import HTTPServer

from modules.api.checks.error_shape import run_error_shape_check
from modules.api.checks.pagination import run_pagination_check
from modules.api.models import API_RESULT_SCHEMA_VERSION, ApiCheckResult, ApiIssue
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
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    }
                                }
                            },
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


def test_empty_page_returning_error_flags_pagination_finding(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_paginated_spec()), encoding="utf-8")
    httpserver.expect_request("/items", method="GET").respond_with_data(
        '{"error":"not found"}', status=404, content_type="application/json"
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_pagination_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "PAGINATION-EMPTY-PAGE-ERROR" for issue in result.issues)


def test_well_behaved_pagination_produces_no_findings(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_paginated_spec()), encoding="utf-8")
    httpserver.expect_request("/items", method="GET").respond_with_json([], status=200)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_pagination_check(client=client, doc=doc, config=api_config)
    assert result.issues == ()


def test_error_shape_detects_distinct_envelopes_per_endpoint(
    api_config: RootConfig,
) -> None:
    """Two distinct rule_ids on the same endpoint → ERROR-SHAPE-DRIFT finding."""

    issue_a = ApiIssue(
        rule_id="CONTRACT-STATUS",
        severity="medium",
        confidence=0.8,
        title="boom",
        description="probe a",
        method="GET",
        route="/items",
        observed_status=500,
        recommendation="fix",
    )
    issue_b = ApiIssue(
        rule_id="CONTRACT-CONTENT-TYPE",
        severity="medium",
        confidence=0.8,
        title="boom",
        description="probe b",
        method="GET",
        route="/items",
        observed_status=500,
        recommendation="fix",
    )
    contract_result = ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="contract",
        issues=(issue_a, issue_b),
        targets_scanned=1,
        duration_ms=1,
    )
    result = run_error_shape_check(results=(contract_result,), config=api_config)
    assert any(issue.rule_id == "ERROR-SHAPE-DRIFT" for issue in result.issues)


def test_error_shape_quiet_when_single_envelope_per_endpoint(
    api_config: RootConfig,
) -> None:
    issue = ApiIssue(
        rule_id="CONTRACT-STATUS",
        severity="medium",
        confidence=0.8,
        title="boom",
        description="probe",
        method="GET",
        route="/items",
        observed_status=500,
        recommendation="fix",
    )
    contract_result = ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="contract",
        issues=(issue,),
        targets_scanned=1,
        duration_ms=1,
    )
    result = run_error_shape_check(results=(contract_result,), config=api_config)
    assert result.issues == ()
