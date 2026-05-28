"""Shared module contract for SentinelQA audit modules (CLAUDE.md §9).

Every capability module (functional, accessibility, performance, etc.)
implements the abstract :class:`SentinelModule` defined in
:mod:`engine.modules.base`. Concrete implementations live under
``modules/<name>/`` so they are obviously separable from the orchestrator
and ready for Phase 24's plugin discovery.

Phase 10 ships the first concrete implementation (``FunctionalModule``);
later module phases (11, 12, 13, 19, 21, 22, 23) reuse the same contract.
"""

from __future__ import annotations

from engine.modules.base import (
    ModuleContext,
    ModulePrerequisiteError,
    SentinelModule,
    build_finding_from_failed_test,
    derive_module_status,
)

__all__ = [
    "ModuleContext",
    "ModulePrerequisiteError",
    "SentinelModule",
    "build_finding_from_failed_test",
    "derive_module_status",
]
