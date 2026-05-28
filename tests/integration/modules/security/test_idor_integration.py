"""Integration tests — IDOR smoke (Phase 13.07)."""

from __future__ import annotations

from pathlib import Path

from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from modules.security.checks.idor import run_idor_check
from tests.integration.modules.security.conftest import make_ctx


def test_idor_finds_cross_user_access(httpserver: HTTPServer, tmp_path: Path) -> None:
    """Endpoint returns 200 for any user id — IDOR detected."""

    def echo(request):  # type: ignore[no-untyped-def]
        return Response('{"id": 1, "secret": "x"}', status=200)

    httpserver.expect_request("/users/1").respond_with_handler(echo)
    httpserver.expect_request("/users/me").respond_with_handler(echo)
    auth_block = "auth:\n" "  second_user:\n" "    token_env: TEST_TOKEN\n"
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/users/42",),
        auth_block=auth_block,
    )
    ctx = ctx.__class__(
        run_id=ctx.run_id,
        target=ctx.target,
        routes=ctx.routes,
        config=ctx.config,
        safety=ctx.safety,
        client=ctx.client,
        audit_log_path=ctx.audit_log_path,
        env={"TEST_TOKEN": "fake-token"},
    )
    try:
        result = run_idor_check(ctx)
    finally:
        ctx.client.close()
    assert any(i.rule_id == "SEC-IDOR-CROSS-USER-ACCESS" for i in result.issues)


def test_idor_no_finding_on_403(httpserver: HTTPServer, tmp_path: Path) -> None:
    def forbid(request):  # type: ignore[no-untyped-def]
        return Response("forbidden", status=403)

    httpserver.expect_request("/users/1").respond_with_handler(forbid)
    httpserver.expect_request("/users/me").respond_with_handler(forbid)
    auth_block = "auth:\n" "  second_user:\n" "    token_env: TEST_TOKEN\n"
    ctx = make_ctx(
        base_url=httpserver.url_for(""),
        tmp_path=tmp_path,
        routes=("/users/42",),
        auth_block=auth_block,
    )
    ctx = ctx.__class__(
        run_id=ctx.run_id,
        target=ctx.target,
        routes=ctx.routes,
        config=ctx.config,
        safety=ctx.safety,
        client=ctx.client,
        audit_log_path=ctx.audit_log_path,
        env={"TEST_TOKEN": "fake-token"},
    )
    try:
        result = run_idor_check(ctx)
    finally:
        ctx.client.close()
    assert all(i.rule_id != "SEC-IDOR-CROSS-USER-ACCESS" for i in result.issues)
