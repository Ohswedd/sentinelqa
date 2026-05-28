"""Shared context object handed to every check.

Encapsulates the bits a check actually needs (HTTP client, target URL,
config, safety decision, audit-log path) without exposing the whole
:class:`engine.orchestrator.run_lifecycle.LifecycleContext`. This keeps
checks easy to unit-test.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from engine.config.schema import RootConfig
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class CheckContext:
    """Immutable inputs threaded to a single check.

    The HTTP client is configured by the module once and shared across
    checks so connection pooling, headers, and timeouts stay consistent
    (CLAUDE §7 — adapters at the boundary).
    """

    run_id: str
    target: Target
    routes: tuple[str, ...]
    config: RootConfig
    safety: SafetyDecision
    client: httpx.Client
    audit_log_path: Path | None
    env: Mapping[str, str] = field(default_factory=dict)
    """Environment-variable snapshot — never holds plaintext secrets."""

    @property
    def target_base_url(self) -> str:
        return str(self.target.base_url)


__all__ = ["CheckContext"]
