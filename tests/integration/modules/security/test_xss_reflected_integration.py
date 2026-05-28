"""Integration tests — reflected XSS (Phase 13.05)."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer

from modules.security.checks.xss_reflected import run_xss_reflected_check
from tests.integration.modules.security.conftest import make_ctx


def test_reflected_endpoint_flagged(httpserver: HTTPServer, tmp_path: Path) -> None:
    def echo(request):  # type: ignore[no-untyped-def]
        q = request.args.get("q", "")
        from werkzeug.wrappers import Response  # pytest-httpserver dep

        return Response(f"<html>echo: {q}</html>", status=200)

    httpserver.expect_request("/search").respond_with_handler(echo)
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/search?q=hi",),
    )
    try:
        result = run_xss_reflected_check(ctx)
    finally:
        ctx.client.close()
    assert any(i.rule_id == "SEC-XSS-REFLECTED" for i in result.issues)
    # Audit log must mention the marker probe.
    assert (tmp_path / "audit.log").exists()
    log = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert "security.xss_reflected.probe" in log
