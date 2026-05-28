"""Unit tests for the stored-XSS gated check (Phase 13.05)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import yaml
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision

from modules.security.checks.context import CheckContext
from modules.security.checks.xss_stored import (
    MARKER,
    PAYLOAD,
    run_xss_stored_check,
)


def _write_proof(path: Path, host: str = "localhost") -> Path:
    now = datetime.now(UTC)
    proof = {
        "schema_version": "1",
        "host": host,
        "actor": "tester",
        "scope": ["destructive"],
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "notes": "test fixture",
    }
    path.write_text(yaml.safe_dump(proof), encoding="utf-8")
    return path


def _ctx_authorized(
    tmp_path: Path,
    transport: httpx.MockTransport,
) -> CheckContext:
    proof_path = _write_proof(tmp_path / "proof.yaml")
    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: http://localhost:8088\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n"
        f"  proof_of_authorization: {proof_path}\n"
        "security:\n"
        "  mode: authorized_destructive\n"
        "  checks:\n"
        "    xss_stored: true\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg_text, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="authorized_destructive",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    client = httpx.Client(
        base_url="http://localhost:8088",
        transport=transport,
        timeout=5.0,
    )
    return CheckContext(
        run_id="RUN-AAAAAAAAAAAA",
        target=target,
        routes=("/",),
        config=config,
        safety=safety,
        client=client,
        audit_log_path=tmp_path / "audit.log",
        env={},
    )


def test_skipped_when_check_disabled(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(routes=("/",))
    result = run_xss_stored_check(ctx)
    assert result.skipped is True
    assert result.skipped_reason and "xss_stored" in result.skipped_reason


def test_skipped_when_safe_mode_even_with_destructive_off(make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = "security:\n  mode: safe\n  checks:\n    xss_stored: false\n"
    ctx = make_ctx(security_block=block, routes=("/",))
    result = run_xss_stored_check(ctx)
    assert result.skipped is True


def test_runs_when_authorized_destructive_with_proof(tmp_path: Path) -> None:
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            if posts:
                return httpx.Response(
                    200,
                    html=f"<html><body>Saved: {PAYLOAD}</body></html>",
                )
            return httpx.Response(
                200,
                html=(
                    """<form method="post" action="/comment">"""
                    """<input type="text" name="body"></form>"""
                ),
            )
        posts.append(request.content.decode("utf-8", errors="ignore"))
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    ctx = _ctx_authorized(tmp_path, transport)
    try:
        result = run_xss_stored_check(ctx)
    finally:
        ctx.client.close()
    assert result.skipped is False
    assert len(posts) == 1
    assert MARKER in posts[0]
    assert any(i.rule_id == "SEC-XSS-STORED" for i in result.issues)
