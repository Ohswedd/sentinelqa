"""Phase 22.05 — auth-matrix check integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.schema import ApiAuthTestUser, ApiConfig, RootConfig
from pytest_httpserver import HTTPServer

from modules.api.checks.auth import run_auth_check
from modules.api.openapi import load_openapi


def _authenticated_spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
        "security": [{"bearer": []}],
        "paths": {
            "/admin/users": {
                "get": {
                    "operationId": "list_users",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": {"type": "object"}}
                                }
                            },
                        },
                        "401": {"description": "unauthorized"},
                    },
                }
            }
        },
    }


@pytest.fixture
def api_config_with_users() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(
            auth_test_users=(
                ApiAuthTestUser(label="user_b", token_env="SENTINEL_TEST_USER_B_TOKEN"),
            )
        ),
    )


def test_anonymous_2xx_to_authenticated_endpoint_is_critical(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config_with_users: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_authenticated_spec()), encoding="utf-8")
    # Vulnerable server: always 200, regardless of Authorization header.
    httpserver.expect_request("/admin/users", method="GET").respond_with_json([], status=200)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_auth_check(
            client=client,
            doc=doc,
            config=api_config_with_users,
            env={"SENTINEL_TEST_USER_B_TOKEN": "user-b-fake"},
        )
    assert any(
        issue.rule_id.startswith("AUTH-UNAUTHORIZED-ANONYMOUS") and issue.severity == "critical"
        for issue in result.issues
    ), [i.model_dump() for i in result.issues]


def test_correctly_protected_endpoint_yields_no_findings(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config_with_users: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_authenticated_spec()), encoding="utf-8")
    httpserver.expect_request("/admin/users", method="GET").respond_with_data("", status=401)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_auth_check(
            client=client,
            doc=doc,
            config=api_config_with_users,
            env={"SENTINEL_TEST_USER_B_TOKEN": "user-b-fake"},
        )
    assert result.issues == ()


def test_no_authenticated_endpoints_returns_skipped(
    httpserver: HTTPServer,
    tmp_path: Path,
) -> None:
    # Spec has no security requirement; auth check skips because no candidates.
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/public": {
                "get": {
                    "operationId": "public_get",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    doc = load_openapi(spec_path)
    config = RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(),
    )
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_auth_check(client=client, doc=doc, config=config, env={})
    assert result.skipped is True
    assert result.skip_reason is not None
    assert "no authenticated" in result.skip_reason


def test_no_doc_with_routes_probes_explicit_routes(
    httpserver: HTTPServer,
) -> None:
    config = RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(routes=("/private",)),
    )
    httpserver.expect_request("/private", method="GET").respond_with_json({"ok": True}, status=200)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_auth_check(client=client, doc=None, config=config, env={})
    # anonymous 200 on a configured route is still critical.
    assert any(issue.rule_id.startswith("AUTH-UNAUTHORIZED-ANONYMOUS") for issue in result.issues)
