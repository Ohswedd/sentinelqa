"""Per-run options for :class:`modules.performance.PerformanceModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PerformanceModuleOptions:
    """Inputs the orchestrator threads into the module via ``ctx.options``.

    Either ``routes`` is provided directly, or ``discovery_path`` points at
    a Phase-05 ``discovery.json`` artifact from which the module derives
    the route list. ``samples`` and ``repeated_nav_samples`` override the
    config defaults when set (non-zero).
    """

    routes: tuple[str, ...] = ()
    discovery_path: Path | None = None
    samples: int | None = None
    repeated_nav_samples: int | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["PerformanceModuleOptions"]
