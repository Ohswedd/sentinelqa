"""Additional coverage for the auth check."""

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


def _auth_spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
        "security": [{"bearer": []}],
        "paths": {
            "/profile": {
                "get": {
                    "operationId": "me",
                    "responses": {"200": {"description": "ok"}, "401": {"description": "no"}},
                }
            }
        },
    }


@pytest.fixture
def config_with_user() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(
            auth_test_users=(
                ApiAuthTestUser(label="user_b", token_env="SENTINEL_TEST_USER_B_TOKEN"),
            )
        ),
    )


def test_cross_user_probe_flags_high_when_authorized(
    httpserver: HTTPServer,
    tmp_path: Path,
    config_with_user: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_auth_spec()), encoding="utf-8")
    httpserver.expect_request("/profile", method="GET").respond_with_json({}, status=200)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_auth_check(
            client=client,
            doc=doc,
            config=config_with_user,
            env={"SENTINEL_TEST_USER_B_TOKEN": "user-b-fake"},
        )
    # Both anonymous-critical and cross-user-high should appear; we
    # specifically assert the cross-user variant was emitted.
    assert any(
        "CROSS_USER" in issue.rule_id and issue.severity == "high" for issue in result.issues
    ), [i.rule_id for i in result.issues]


def test_cross_user_token_missing_env_skips_cross_user_probe(
    httpserver: HTTPServer,
    tmp_path: Path,
    config_with_user: RootConfig,
) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_auth_spec()), encoding="utf-8")
    # Server still vulnerable for anonymous; cross-user can't be tested
    # because the env doesn't carry the token.
    httpserver.expect_request("/profile", method="GET").respond_with_json({}, status=200)
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_auth_check(
            client=client,
            doc=doc,
            config=config_with_user,
            env={},  # empty env
        )
    rule_ids = {issue.rule_id for issue in result.issues}
    assert all("CROSS_USER" not in r for r in rule_ids)
