"""Shared fixtures for integration tests using ``pytest-httpserver``."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision
from pytest_httpserver import HTTPServer

from modules.security.checks.context import CheckContext


@pytest.fixture
def vulnerable_server(httpserver: HTTPServer) -> Iterator[HTTPServer]:
    """An ``HTTPServer`` already wired to the canonical vulnerable fixture."""

    yield httpserver


def make_ctx(
    *,
    base_url: str,
    tmp_path: Path,
    routes: tuple[str, ...] = ("/",),
    security_block: str = "",
    auth_block: str = "",
) -> CheckContext:
    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        f"  base_url: {base_url}\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n"
    )
    if auth_block:
        cfg_text += auth_block
    if security_block:
        cfg_text += security_block
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
        mode=config.security.mode,
        allowed=True,
        reason="integration_fixture",
        decided_at=datetime.now(UTC),
    )
    client = httpx.Client(base_url=base_url, timeout=5.0)
    return CheckContext(
        run_id="RUN-AAAAAAAAAAAA",
        target=target,
        routes=routes,
        config=config,
        safety=safety,
        client=client,
        audit_log_path=tmp_path / "audit.log",
        env={},
    )


__all__ = ["make_ctx", "vulnerable_server"]
