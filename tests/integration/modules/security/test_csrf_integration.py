"""Integration tests — CSRF check."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer

from modules.security.checks.csrf import run_csrf_check
from tests.integration.modules.security.conftest import make_ctx


def test_form_without_token_high(httpserver: HTTPServer, tmp_path: Path) -> None:
    httpserver.expect_request("/profile").respond_with_data(
        """<html><body><form method="post" action="/save">"""
        """<input name="email"></form></body></html>""",
    )
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/profile",),
    )
    try:
        result = run_csrf_check(ctx)
    finally:
        ctx.client.close()
    assert any(
        i.rule_id == "SEC-CSRF-MISSING-TOKEN" and i.severity == "high" for i in result.issues
    )
