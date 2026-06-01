"""Integration tests — stored XSS gate."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer

from modules.security.checks.xss_stored import run_xss_stored_check
from tests.integration.modules.security.conftest import make_ctx


def test_safe_mode_skips_stored_xss(httpserver: HTTPServer, tmp_path: Path) -> None:
    httpserver.expect_request("/").respond_with_data("<html></html>")
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/",),
    )
    try:
        result = run_xss_stored_check(ctx)
    finally:
        ctx.client.close()
    assert result.skipped is True
