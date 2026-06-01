"""Shared fixtures for security-module unit tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.loader import load_config
from engine.config.schema import RootConfig
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision

from modules.security.checks.context import CheckContext


def _write_config(
    root: Path,
    *,
    base_url: str = "http://localhost:8088",
    security_block: str = "",
    auth_block: str = "",
) -> Path:
    p = root / "sentinel.config.yaml"
    body = (
        "version: 1\n"
        "project:\n  name: app\n"
        f"target:\n  base_url: {base_url}\n  allowed_hosts: [localhost, 127.0.0.1]\n"
    )
    if auth_block:
        body += auth_block
    if security_block:
        body += security_block
    p.write_text(body, encoding="utf-8")
    return p


def make_check_context(
    tmp_path: Path,
    *,
    routes: tuple[str, ...] = ("/",),
    base_url: str = "http://localhost:8088",
    security_block: str = "",
    auth_block: str = "",
    transport: httpx.BaseTransport | None = None,
    audit_log_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[CheckContext, httpx.Client]:
    """Build a :class:`CheckContext` against a controlled httpx transport."""

    cfg_path = _write_config(
        tmp_path,
        base_url=base_url,
        security_block=security_block,
        auth_block=auth_block,
    )
    config: RootConfig = load_config(cfg_path)
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
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    client = httpx.Client(
        base_url=base_url,
        transport=transport,
        timeout=5.0,
    )
    audit_log = audit_log_path or (tmp_path / "audit.log")
    ctx = CheckContext(
        run_id="RUN-AAAAAAAAAAAA",
        target=target,
        routes=routes,
        config=config,
        safety=safety,
        client=client,
        audit_log_path=audit_log,
        env=env or {},
    )
    return ctx, client


@pytest.fixture
def make_ctx(tmp_path: Path) -> Iterator[Any]:
    """Factory fixture yielding a builder bound to ``tmp_path``."""

    clients: list[httpx.Client] = []

    def _factory(**kwargs: Any) -> CheckContext:
        ctx, client = make_check_context(tmp_path, **kwargs)
        clients.append(client)
        return ctx

    yield _factory

    for c in clients:
        c.close()


__all__ = ["make_check_context", "make_ctx"]
