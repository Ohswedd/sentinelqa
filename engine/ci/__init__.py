"""SentinelQA CI integration core (Phase 17).

Public surface:

- :class:`CiMode` — typed alias for the five mode names (the documentation).
- :class:`ModePlan` — the resolved preset (modules + tag filter + policy
  overrides).
- :func:`apply_mode` — pure function that turns a ``RootConfig`` + mode
  into the effective config + plan.

The engine never imports `apps/cli` or `integrations/*`;
this package is the integration point both consume.
"""

from __future__ import annotations

from engine.ci.diff_aware import (
    DEFAULT_MAX_CHANGED_FILES,
    SMOKE_TAG,
    DiffSelection,
    select_from_files,
    select_from_git,
)
from engine.ci.modes import (
    CI_MODES,
    DEFAULT_CI_MODE,
    CiMode,
    InvalidCiModeError,
    ModePlan,
    apply_mode,
    enabled_modules,
    grep_for_mode,
    mode_plan,
)

__all__ = [
    "CI_MODES",
    "DEFAULT_CI_MODE",
    "DEFAULT_MAX_CHANGED_FILES",
    "CiMode",
    "DiffSelection",
    "InvalidCiModeError",
    "ModePlan",
    "SMOKE_TAG",
    "apply_mode",
    "enabled_modules",
    "grep_for_mode",
    "mode_plan",
    "select_from_files",
    "select_from_git",
]
