"""Unit tests for the SQLi safe probe (Phase 13.06)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision

from modules.security.checks.context import CheckContext
from modules.security.checks.sqli import run_sqli_check


def test_skipped_when_disabled(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(routes=("/search?q=hi",))
    result = run_sqli_check(ctx)
    assert result.skipped is True
    assert result.skipped_reason and "sqli" in result.skipped_reason


def test_runs_on_local_target_when_enabled(make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = "security:\n  checks:\n    sqli: true\n"

    from urllib.parse import unquote_plus

    def handler(request: httpx.Request) -> httpx.Response:
        # Simulate behavioural difference between true/false payloads.
        query = unquote_plus(request.url.query.decode("utf-8"))
        if "'1'='1" in query or "1 OR 1=1" in query:
            return httpx.Response(200, text="A" * 1000)
        if "'1'='2" in query or "1 AND 1=0" in query:
            return httpx.Response(200, text="A" * 100)
        return httpx.Response(200, text="A" * 100)

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, security_block=block, routes=("/search?q=hi",))
    result = run_sqli_check(ctx)
    assert result.skipped is False
    assert any(i.rule_id == "SEC-SQLI-BEHAVIORAL" for i in result.issues)


def test_skipped_for_non_local_target_without_proof(tmp_path: Path) -> None:
    # Build a context whose target is non-local; sqli should refuse.
    cfg = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: https://example.com\n"
        "  allowed_hosts: [example.com]\n"
        "security:\n"
        "  checks:\n"
        "    sqli: true\n"
    )
    p = tmp_path / "sentinel.config.yaml"
    p.write_text(cfg, encoding="utf-8")
    config = load_config(p)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
    )
    safety = SafetyDecision(
        host="example.com",
        mode="safe",
        allowed=True,
        reason="test",
        decided_at=datetime.now(UTC),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="https://example.com", transport=transport)
    try:
        ctx = CheckContext(
            run_id="RUN-AAAAAAAAAAAA",
            target=target,
            routes=("/search?q=x",),
            config=config,
            safety=safety,
            client=client,
            audit_log_path=tmp_path / "audit.log",
            env={},
        )
        result = run_sqli_check(ctx)
    finally:
        client.close()
    assert result.skipped is True
    assert "destructive" in (result.skipped_reason or "").lower()


def test_skipped_when_no_query_string(make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = "security:\n  checks:\n    sqli: true\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, security_block=block, routes=("/",))
    result = run_sqli_check(ctx)
    # The check enables but finds no injectable param; no findings emitted.
    assert result.skipped is False
    assert result.issues == ()
