"""Inputs the CLI / orchestrator hands to :class:`ChaosModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ChaosModuleOptions:
    """Per-run options. CLI flags map here; config supplies defaults.

    Empty tuples / ``None`` values mean "fall back to
    ``config.chaos.<field>``". ``events_path`` lets the caller point at
    a pre-recorded JSONL of :class:`modules.chaos.models.ChaosEvent` —
    used by the integration tests (and by re-runs that ingest chaos
    output produced by an external Playwright invocation).
    """

    enabled_categories: tuple[str, ...] = field(default_factory=tuple)
    enabled_scenarios: tuple[str, ...] = field(default_factory=tuple)
    flows: tuple[str, ...] = field(default_factory=tuple)
    events_path: Path | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["ChaosModuleOptions"]
