"""Per-run options the orchestrator threads into the LLM-audit module."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LlmAuditModuleOptions:
    """Inputs the CLI / orchestrator hands to the module.

    Each field is optional. ``checks`` lets callers run a subset
    (our engineering rules: ``--checks <subset>`` on the CLI); when empty, the
    module runs every registered check whose signals are available.
    ``discovery_path`` lets callers replay a artifact instead
    of re-discovering. ``signals_root`` is the directory the module
    walks for optional runtime signals captured by earlier phases.
    """

    discovery_path: Path | None = None
    signals_root: Path | None = None
    checks: tuple[str, ...] = field(default_factory=tuple)
    third_party_console_hosts: tuple[str, ...] = field(default_factory=tuple)
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["LlmAuditModuleOptions"]
