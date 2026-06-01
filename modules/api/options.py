"""Inputs the CLI / orchestrator hands to :class:`ApiModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ApiModuleOptions:
    """Per-run options. CLI flags map here; config supplies defaults.

    Each field is optional; ``None`` / empty values mean "fall back to
    ``config.api.<field>``" (handled by :class:`ApiModule`). The
    ``diff_since_run_id`` knob is intentionally CLI-only — backward
    compatibility checks always need an operator-confirmed reference
    run rather than a silent config default.
    """

    routes: tuple[str, ...] = field(default_factory=tuple)
    openapi_path: Path | None = None
    graphql_path: Path | None = None
    discovery_path: Path | None = None
    enabled_checks: tuple[str, ...] = field(default_factory=tuple)
    diff_since_run_id: str | None = None
    artifacts_root: Path | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["ApiModuleOptions"]
