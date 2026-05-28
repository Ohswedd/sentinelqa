"""Integration tests — security headers against a real HTTP server (Phase 13.02)."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer

from modules.security.checks.headers import run_headers_check
from tests.integration.modules.security.conftest import make_ctx


def test_full_headers_yields_no_findings(httpserver: HTTPServer, tmp_path: Path) -> None:
    httpserver.expect_request("/").respond_with_data(
        "ok",
        headers={
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=()",
        },
    )
    ctx = make_ctx(base_url=httpserver.url_for(""), tmp_path=tmp_path)
    try:
        result = run_headers_check(ctx)
    finally:
        ctx.client.close()
    assert result.issues == ()


def test_missing_headers_yields_expected_severities(httpserver: HTTPServer, tmp_path: Path) -> None:
    httpserver.expect_request("/").respond_with_data("ok", headers={})
    ctx = make_ctx(base_url=httpserver.url_for(""), tmp_path=tmp_path)
    try:
        result = run_headers_check(ctx)
    finally:
        ctx.client.close()
    ids = {(i.rule_id, i.severity) for i in result.issues}
    assert ("SEC-HEADERS-CSP-MISSING", "high") in ids
    assert ("SEC-HEADERS-XCONTENT-NOSNIFF-MISSING", "medium") in ids
    assert ("SEC-HEADERS-REFERRER-POLICY-MISSING", "low") in ids
