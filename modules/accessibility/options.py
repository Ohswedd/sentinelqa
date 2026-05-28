"""Per-run options for :class:`modules.accessibility.AccessibilityModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AccessibilityModuleOptions:
    """Inputs the orchestrator threads into the module via ``ctx.options``.

    Either ``routes`` is provided directly, or ``discovery_path`` points at
    a Phase-05 ``discovery.json`` artifact from which the module derives
    the route list. ``axe_tags`` overrides ``config.accessibility.axe.tags``.
    """

    routes: tuple[str, ...] = ()
    discovery_path: Path | None = None
    axe_tags: tuple[str, ...] | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["AccessibilityModuleOptions"]
