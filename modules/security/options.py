"""Per-run options for :class:`modules.security.SecurityModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SecurityModuleOptions:
    """Inputs the orchestrator threads into the module via ``ctx.options``.

    The CLI fills these in based on ``--url``, ``--routes``, ``--checks``,
    ``--mode``, and ``--proof-of-authorization`` flags. When the SDK or
    a direct lifecycle caller provides nothing, the module falls back to
    ``config.security`` (routes / checks).
    """

    routes: tuple[str, ...] = ()
    discovery_path: Path | None = None
    enabled_checks: tuple[str, ...] = ()
    """Override ``config.security.checks`` when non-empty (intersected with safety rules)."""
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["SecurityModuleOptions"]
