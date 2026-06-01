"""Shared safety helper for URL-bearing tools (ADR-0023 safety contract).

Every our product spec tool that takes a ``url`` argument calls
:func:`enforce_url` before any SDK call. This module is the single
chokepoint so the AST-level safety guard
(`tests/security/test_mcp_safety.py`) only needs to look for one
function name.
"""

from __future__ import annotations

from pathlib import Path

from engine.domain.target import Target
from engine.errors.base import UnsafeTargetError
from engine.policy.safety import SafetyPolicy
from pydantic import AnyUrl

from sentinelqa_mcp.tools import ToolContext


def enforce_url(url: str, context: ToolContext) -> None:
    """Run the canonical SafetyPolicy on ``url`` before any I/O.

    Raises :class:`engine.errors.UnsafeTargetError` (exit code 4)
    when the target is not allowed. The server's dispatcher catches
    that and renders it as an ``UNSAFE_TARGET`` envelope.
    """

    config = context.sentinel.policy()  # pulls allowed_hosts from config
    allowed_hosts = frozenset(config.allowed_hosts)
    target = Target(
        base_url=AnyUrl(url),
        allowed_hosts=allowed_hosts,
        mode=config.mode,
        proof_of_authorization=config.proof_of_authorization,
    )
    audit_log = _audit_log_path(context.project_path)
    SafetyPolicy().enforce(target, audit_log_path=audit_log)


def _audit_log_path(project_path: Path) -> Path:
    log_dir = project_path / ".sentinel" / "mcp-audit"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "audit.log"


__all__ = ["UnsafeTargetError", "enforce_url"]
