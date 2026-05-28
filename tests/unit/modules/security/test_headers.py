"""Unit tests for the security headers check (Phase 13.02)."""

from __future__ import annotations

from typing import cast

import httpx

from modules.security.checks.context import CheckContext
from modules.security.checks.headers import _evaluate, run_headers_check


def _ids(issues) -> set[str]:
    return {i.rule_id for i in issues}


def test_evaluate_https_missing_all_yields_all_findings() -> None:
    issues = list(_evaluate(route="/", is_https=True, headers={}))
    ids = _ids(issues)
    assert "SEC-HEADERS-HSTS-MISSING" in ids
    assert "SEC-HEADERS-CSP-MISSING" in ids
    assert "SEC-HEADERS-XFRAME-MISSING" in ids
    assert "SEC-HEADERS-XCONTENT-NOSNIFF-MISSING" in ids
    assert "SEC-HEADERS-REFERRER-POLICY-MISSING" in ids
    assert "SEC-HEADERS-PERMISSIONS-POLICY-MISSING" in ids


def test_evaluate_http_skips_hsts() -> None:
    issues = list(_evaluate(route="/", is_https=False, headers={}))
    ids = _ids(issues)
    assert "SEC-HEADERS-HSTS-MISSING" not in ids
    # Everything else still required.
    assert "SEC-HEADERS-CSP-MISSING" in ids


def test_evaluate_csp_unsafe_inline_flagged() -> None:
    issues = list(
        _evaluate(
            route="/",
            is_https=True,
            headers={
                "content-security-policy": "default-src 'self'; script-src 'self' 'unsafe-inline'",
            },
        )
    )
    ids = _ids(issues)
    assert "SEC-HEADERS-CSP-UNSAFE-INLINE" in ids
    assert "SEC-HEADERS-CSP-MISSING" not in ids


def test_evaluate_csp_frame_ancestors_satisfies_xframe() -> None:
    issues = list(
        _evaluate(
            route="/",
            is_https=True,
            headers={
                "content-security-policy": "default-src 'self'; frame-ancestors 'self'",
            },
        )
    )
    ids = _ids(issues)
    assert "SEC-HEADERS-XFRAME-MISSING" not in ids


def test_evaluate_full_headers_no_findings() -> None:
    headers = {
        "strict-transport-security": "max-age=31536000",
        "content-security-policy": "default-src 'self'",
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "permissions-policy": "camera=()",
    }
    issues = list(_evaluate(route="/", is_https=True, headers=headers))
    assert issues == []


def test_run_headers_check_against_stubbed_transport(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return httpx.Response(405)
        return httpx.Response(200, headers={})

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/", "/login"))
    result = run_headers_check(ctx)
    assert result.check == "headers"
    assert result.targets_scanned == 2
    assert any(i.rule_id == "SEC-HEADERS-CSP-MISSING" for i in result.issues)
    # Local HTTP target → no HSTS finding.
    assert not any(i.rule_id == "SEC-HEADERS-HSTS-MISSING" for i in result.issues)


def test_run_headers_check_logs_per_route_audit(make_ctx) -> None:  # type: ignore[no-untyped-def]
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, headers={"content-security-policy": "default-src 'self'"})

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/a", "/b"))
    run_headers_check(ctx)
    log = cast(CheckContext, ctx).audit_log_path
    assert log is not None
    assert log.exists()
    text = log.read_text(encoding="utf-8")
    assert "security.headers.probe" in text
    assert "/a" in text and "/b" in text


def test_run_headers_check_skips_unreachable_route(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if "fail" in request.url.path:
            raise httpx.ConnectError("simulated")
        return httpx.Response(200, headers={})

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/fail", "/ok"))
    result = run_headers_check(ctx)
    assert result.targets_scanned == 1
