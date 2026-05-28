"""Integration tests — frontend secrets (Phase 13.08)."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from modules.security.checks.frontend_secrets import run_frontend_secrets_check
from tests.integration.modules.security.conftest import make_ctx


def test_aws_key_in_real_bundle(httpserver: HTTPServer, tmp_path: Path) -> None:
    def page_handler(request):  # type: ignore[no-untyped-def]
        return Response(
            """<html><body><script src="/app.js"></script></body></html>""",
            status=200,
        )

    def bundle_handler(request):  # type: ignore[no-untyped-def]
        return Response(
            "const cfg = { ak: 'AKIAIOSFODNN7EXAMPLE' };",
            status=200,
            content_type="application/javascript",
        )

    httpserver.expect_request("/").respond_with_handler(page_handler)
    httpserver.expect_request("/app.js").respond_with_handler(bundle_handler)
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/",),
    )
    try:
        result = run_frontend_secrets_check(ctx)
    finally:
        ctx.client.close()
    assert any(i.rule_id == "SEC-FRONTEND-SECRET-IN-BUNDLE" for i in result.issues)
