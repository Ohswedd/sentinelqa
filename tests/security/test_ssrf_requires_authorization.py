"""``ssrf_redirect`` refuses to run without destructive-mode + PoA."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.errors.base import ConfigError
from engine.policy.safety import SafetyDecision

from modules.security.checks.context import CheckContext
from modules.security.checks.ssrf_redirect import UrlInput, run_ssrf_redirect_check


def _ctx(tmp_path: Path) -> CheckContext:
    cfg = tmp_path / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:8088\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n",
        encoding="utf-8",
    )
    config = load_config(cfg)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    return CheckContext(
        run_id="RUN-AAAAAAAAAAAA",
        target=target,
        routes=("/",),
        config=config,
        safety=safety,
        client=httpx.Client(base_url="http://localhost:8088"),
        audit_log_path=tmp_path / "audit.log",
    )


def test_ssrf_refuses_without_destructive_mode(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    try:
        with pytest.raises(ConfigError, match="authorized_destructive"):
            run_ssrf_redirect_check(
                ctx,
                inputs=(
                    UrlInput(
                        method="GET",
                        url="https://api/proxy",
                        parameter="url",
                    ),
                ),
            )
    finally:
        ctx.client.close()
