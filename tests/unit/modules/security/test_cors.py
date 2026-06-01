"""Unit tests for the CORS check."""

from __future__ import annotations

import httpx

from modules.security.checks.cors import SYNTHETIC_ORIGIN, run_cors_check


def test_wildcard_acao_plus_credentials_is_critical(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "OPTIONS":
            return httpx.Response(405)
        return httpx.Response(
            204,
            headers={
                "access-control-allow-origin": "*",
                "access-control-allow-credentials": "true",
            },
        )

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/api/data",))
    result = run_cors_check(ctx)
    ids = {(i.rule_id, i.severity) for i in result.issues}
    assert ("SEC-CORS-WILDCARD-CREDENTIALS", "critical") in ids


def test_reflective_acao_is_high(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        origin = request.headers.get("origin", "")
        return httpx.Response(
            204,
            headers={
                "access-control-allow-origin": origin,
            },
        )

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/api/data",))
    result = run_cors_check(ctx)
    ids = {i.rule_id for i in result.issues}
    assert "SEC-CORS-REFLECTIVE-ALLOW-ORIGIN" in ids


def test_no_cors_headers_no_findings(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/api/data",))
    result = run_cors_check(ctx)
    assert result.issues == ()
    assert result.targets_scanned == 1


def test_synthetic_origin_is_invalid_tld() -> None:
    assert SYNTHETIC_ORIGIN.endswith(".invalid")
