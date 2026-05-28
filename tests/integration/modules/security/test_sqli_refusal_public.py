"""Integration tests — SQLi refusal vs public targets (Phase 13.06)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision

from modules.security.checks.context import CheckContext
from modules.security.checks.sqli import run_sqli_check


def test_sqli_refused_on_public_target_without_proof(tmp_path: Path) -> None:
    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: https://example.com\n"
        "  allowed_hosts: [example.com]\n"
        "security:\n"
        "  checks:\n"
        "    sqli: true\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg_text, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
    )
    safety = SafetyDecision(
        host="example.com",
        mode="safe",
        allowed=True,
        reason="public_host_in_allowlist",
        decided_at=datetime.now(UTC),
    )
    client = httpx.Client(base_url="https://example.com", timeout=2.0)
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
    assert result.skipped_reason and "destructive" in result.skipped_reason.lower()
