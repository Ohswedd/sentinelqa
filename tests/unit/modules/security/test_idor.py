"""Unit tests for the IDOR smoke check (Phase 13.07)."""

from __future__ import annotations

import httpx

from modules.security.checks.idor import (
    _candidate_segments,
    _replace_segment,
    run_idor_check,
)


def test_candidate_segments_finds_numeric_and_hex() -> None:
    assert _candidate_segments("/api/users/42") == [(2, "42")]
    assert _candidate_segments("/orders/9f1aa3bb") == [(1, "9f1aa3bb")]
    assert _candidate_segments("/about") == []


def test_replace_segment_round_trip() -> None:
    assert _replace_segment("/api/users/42", 2, "me") == "/api/users/me"
    assert _replace_segment("/orders/", 0, "1") == "/1/"


def test_skipped_without_second_user_token(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(routes=("/api/users/42",))
    result = run_idor_check(ctx)
    assert result.skipped is True
    assert "second-user token" in (result.skipped_reason or "")


def test_finds_idor_when_other_user_200(make_ctx) -> None:  # type: ignore[no-untyped-def]
    auth_block = (
        "auth:\n"
        "  strategy: api_key\n"
        "  second_user:\n"
        "    token_env: TEST_SECOND_USER_TOKEN\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer fake-token"
        return httpx.Response(200, text='{"id": 1, "secret": "x"}')

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(
        transport=transport,
        auth_block=auth_block,
        routes=("/api/users/42",),
        env={"TEST_SECOND_USER_TOKEN": "fake-token"},
    )
    result = run_idor_check(ctx)
    assert result.skipped is False
    assert any(i.rule_id == "SEC-IDOR-CROSS-USER-ACCESS" for i in result.issues)


def test_no_finding_when_403(make_ctx) -> None:  # type: ignore[no-untyped-def]
    auth_block = (
        "auth:\n"
        "  strategy: api_key\n"
        "  second_user:\n"
        "    token_env: TEST_SECOND_USER_TOKEN\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(
        transport=transport,
        auth_block=auth_block,
        routes=("/api/users/42",),
        env={"TEST_SECOND_USER_TOKEN": "fake-token"},
    )
    result = run_idor_check(ctx)
    assert result.issues == ()
