"""Integration tests — CORS check (Phase 13.04)."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer

from modules.security.checks.cors import run_cors_check
from tests.integration.modules.security.conftest import make_ctx


def test_wildcard_with_credentials_critical(httpserver: HTTPServer, tmp_path: Path) -> None:
    httpserver.expect_request("/api", method="OPTIONS").respond_with_data(
        "",
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
        },
    )
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/api",),
    )
    try:
        result = run_cors_check(ctx)
    finally:
        ctx.client.close()
    assert any(
        i.rule_id == "SEC-CORS-WILDCARD-CREDENTIALS" and i.severity == "critical"
        for i in result.issues
    )
