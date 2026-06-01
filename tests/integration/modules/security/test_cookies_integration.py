"""Integration tests — cookie-flag check."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer

from modules.security.checks.cookies import run_cookies_check
from tests.integration.modules.security.conftest import make_ctx


def test_login_without_secure_flag_high_severity(httpserver: HTTPServer, tmp_path: Path) -> None:
    httpserver.expect_request("/login").respond_with_data(
        "ok",
        headers={"Set-Cookie": "session=abc"},
    )
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/login",),
    )
    try:
        result = run_cookies_check(ctx)
    finally:
        ctx.client.close()
    rules = {(i.rule_id, i.severity) for i in result.issues}
    # Local HTTP — Secure flag not checked (since not HTTPS).
    # But HttpOnly + SameSite still missing, and it's auth-like.
    assert ("SEC-COOKIE-MISSING-HTTPONLY", "high") in rules
    assert any(rid.startswith("SEC-COOKIE-MISSING-SAMESITE") for rid, _ in rules)
