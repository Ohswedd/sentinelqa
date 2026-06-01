"""Integration tests — SQLi probe."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from modules.security.checks.sqli import run_sqli_check
from tests.integration.modules.security.conftest import make_ctx


def test_sqli_behavioral_difference_caught(httpserver: HTTPServer, tmp_path: Path) -> None:
    def diff_handler(request):  # type: ignore[no-untyped-def]
        q = request.args.get("q", "")
        if "'1'='1" in q or "1 OR 1=1" in q:
            return Response("A" * 1000, status=200)
        if "'1'='2" in q or "1 AND 1=0" in q:
            return Response("A" * 50, status=200)
        return Response("baseline", status=200)

    httpserver.expect_request("/search").respond_with_handler(diff_handler)
    block = "security:\n  checks:\n    sqli: true\n"
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/search?q=hi",),
        security_block=block,
    )
    try:
        result = run_sqli_check(ctx)
    finally:
        ctx.client.close()
    assert result.skipped is False
    assert any(i.rule_id == "SEC-SQLI-BEHAVIORAL" for i in result.issues)
