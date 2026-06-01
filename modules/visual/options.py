"""Per-run options threaded into :class:`VisualModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class VisualModuleOptions:
    """Inputs the CLI / orchestrator hands to the visual module.

    - ``current_root``: directory tree of captured PNGs
    (``<viewport>/<route-slug>.png``). Defaults to
    ``<run-dir>/visual/current``.
    - ``baselines_dir``: override the configured baselines directory.
    - ``viewports``: optional subset of configured viewports to run.
    Empty tuple → every configured viewport.
    - ``routes``: optional subset of route slugs (every PNG in
    ``current_root/<viewport>/`` is otherwise considered).
    - ``threshold``: override the configured pixel-diff threshold.
    """

    current_root: Path | None = None
    baselines_dir: Path | None = None
    viewports: tuple[str, ...] = field(default_factory=tuple)
    routes: tuple[str, ...] = field(default_factory=tuple)
    threshold: float | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["VisualModuleOptions"]
