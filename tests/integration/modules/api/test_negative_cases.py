"""Phase 22.04 — negative-case check integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig
from pytest_httpserver import HTTPServer

from modules.api.checks.negative import run_negative_check
from modules.api.http_client import ABSOLUTE_MAX_REQUEST_BYTES, RequestTooLargeError, safe_request
from modules.api.openapi import load_openapi


def _post_spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/users": {
                "post": {
                    "operationId": "create_user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email", "age"],
                                    "properties": {
                                        "email": {"type": "string"},
                                        "age": {"type": "integer", "maximum": 120},
                                        "is_admin": {"type": "boolean"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
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
        api=ApiConfig(),
    )


def test_validation_gap_on_missing_required_field(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_post_spec()), encoding="utf-8")
    # Server accepts every request with 201 — including the missing-required variant.
    httpserver.expect_request("/users", method="POST").respond_with_json({"id": "abc"}, status=201)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_negative_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "NEGATIVE-VALIDATION-GAP" for issue in result.issues), [
        i.model_dump() for i in result.issues
    ]


def test_5xx_on_invalid_input_is_high(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_post_spec()), encoding="utf-8")
    httpserver.expect_request("/users", method="POST").respond_with_data("internal", status=500)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_negative_check(client=client, doc=doc, config=api_config)
    assert any(issue.rule_id == "NEGATIVE-SERVER-ERROR" for issue in result.issues)


def test_well_validated_endpoint_produces_no_findings(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_post_spec()), encoding="utf-8")
    httpserver.expect_request("/users", method="POST").respond_with_data(
        '{"error":"bad request"}', status=400, content_type="application/json"
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_negative_check(client=client, doc=doc, config=api_config)
    # Every variant got rejected with 4xx — no findings.
    assert result.issues == ()


def test_request_above_absolute_cap_rejected_at_client(
    httpserver: HTTPServer,
) -> None:
    """CLAUDE §30 — safe_request must refuse oversized bodies."""

    with (
        httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client,
        pytest.raises(RequestTooLargeError),
    ):
        safe_request(
            client,
            "POST",
            "/users",
            json_body={"x": "A" * (ABSOLUTE_MAX_REQUEST_BYTES + 1024)},
            max_body_kb=ABSOLUTE_MAX_REQUEST_BYTES // 1024 + 16,
        )
