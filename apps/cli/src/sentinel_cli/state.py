"""Mutable global state propagated from the root Typer callback.

Typer's idiomatic way to pass options from a root callback to subcommands
is :class:`typer.Context.obj`. This module owns the dataclass we stash
there so subcommands and tests have a typed handle. Nothing here is
public API — the schema can change without a major version bump.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from engine.log import LogMode

Mode = Literal["human", "json", "quiet"]


def detect_ci_default() -> bool:
    """Honor environment-driven CI detection per CLAUDE §39 and."""

    if os.environ.get("SENTINEL_CI", "").lower() in {"1", "true", "yes"}:
        return True
    return os.environ.get("CI", "").lower() in {"1", "true", "yes"}


@dataclass(slots=True)
class GlobalState:
    """Cross-cutting CLI flags resolved at the root callback.

    Subcommands read this off ``ctx.obj`` instead of redeclaring the same
    options. ``mode`` summarizes the precedence: ``--quiet`` beats
    ``--json`` beats human; CI mode forces JSON unless ``--quiet`` was
    explicitly requested.
    """

    config_path: Path = field(default_factory=lambda: Path("sentinel.config.yaml"))
    json: bool = False
    verbose: bool = False
    quiet: bool = False
    ci: bool = False
    no_color: bool = False
    dry_run: bool = False

    @property
    def mode(self) -> LogMode:
        if self.quiet:
            return "quiet"
        if self.json or self.ci:
            return "json"
        return "human"

    @property
    def log_level(self) -> str:
        if self.quiet:
            return "ERROR"
        if self.verbose:
            return "DEBUG"
        return "INFO"


__all__ = ["GlobalState", "Mode", "detect_ci_default"]
