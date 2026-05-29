"""CI mode presets (PRD §21.3, task 17.04).

Each mode is a preset over three knobs:

- **modules** — which audit modules run (subset of
  :class:`engine.config.schema.ModulesConfig`).
- **grep** — Playwright ``--grep`` value threaded into the functional
  module via the lifecycle ``module_options`` channel.
- **policy_overrides** — a mapping of policy fields the mode raises
  before the lifecycle starts (`release` raises
  ``policy.min_quality_score`` to ``max(config, 90)``).

The underlying :class:`engine.orchestrator.run_lifecycle.RunLifecycle` is
unchanged — modes are entirely a CLI-layer concern that translates into
inputs the lifecycle already accepts (CLAUDE.md §10, §17).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from engine.config.schema import (
    ModulesConfig,
    PolicyConfig,
    RootConfig,
)
from engine.errors.base import ConfigError

CiMode = Literal["fast", "standard", "full", "nightly", "release"]
"""Five PRD §21.3 mode names."""

CI_MODES: Final[tuple[CiMode, ...]] = ("fast", "standard", "full", "nightly", "release")
"""Tuple of all supported mode names in canonical order."""

DEFAULT_CI_MODE: Final[CiMode] = "standard"
"""Default `sentinel ci` mode when ``--mode`` is omitted."""

# Release mode raises the gate floor to this value unless the user has
# already configured something stricter. PRD §21.3 calls this "strict
# policy"; we land on 90 to match the CLAUDE.md §17 "no surprises in
# release" stance without being so high that healthy projects fail.
_RELEASE_MIN_QUALITY_SCORE: Final[int] = 90


class InvalidCiModeError(ConfigError):
    """Raised when ``--mode`` is not one of :data:`CI_MODES`."""

    def __init__(self, *, mode: str) -> None:
        super().__init__(
            detail=(
                f"unknown ci mode {mode!r}; expected one of {', '.join(CI_MODES)} " f"(PRD §21.3)."
            ),
            technical_context={"mode": mode, "supported": list(CI_MODES)},
        )


@dataclass(frozen=True)
class ModePlan:
    """The preset resolved for one ``sentinel ci`` invocation.

    Pure data — the CLI consumes ``modules`` and ``grep``; the lifecycle
    consumes the effective config returned alongside.
    """

    mode: CiMode
    modules: tuple[str, ...]
    grep: str | None
    policy_overrides: Mapping[str, int | float | bool] = field(default_factory=dict)
    extras: Mapping[str, str | int | bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "modules": list(self.modules),
            "grep": self.grep,
            "policy_overrides": dict(self.policy_overrides),
            "extras": dict(self.extras),
        }


# ---------------------------------------------------------------------------
# Mode definitions
# ---------------------------------------------------------------------------


def enabled_modules(cfg: ModulesConfig) -> tuple[str, ...]:
    """Return the user-enabled module names in canonical order.

    Public helper consumed by ``sentinel ci`` to compute the
    full-mode fallback module set when diff-aware selection trips its
    broad-impact tripwire.
    """

    return _modules_from_config(cfg)


def _modules_from_config(cfg: ModulesConfig) -> tuple[str, ...]:
    """Return the user-enabled module names in canonical order."""

    ordered: list[str] = []
    if cfg.functional:
        ordered.append("functional")
    if cfg.api:
        ordered.append("api")
    if cfg.accessibility:
        ordered.append("accessibility")
    if cfg.performance:
        ordered.append("performance")
    if cfg.visual:
        ordered.append("visual")
    if cfg.security:
        ordered.append("security")
    if cfg.chaos:
        ordered.append("chaos")
    if cfg.llm_audit:
        ordered.append("llm_audit")
    return tuple(ordered)


def _intersect_with_config(requested: tuple[str, ...], cfg: ModulesConfig) -> tuple[str, ...]:
    """Drop any module name that is disabled in config (safety boundary)."""

    enabled = set(_modules_from_config(cfg))
    return tuple(name for name in requested if name in enabled)


def grep_for_mode(mode: CiMode) -> str | None:
    """Return the canonical tag filter for ``mode``.

    Mirrors :mod:`modules.functional.tags` so the Phase-10 slice modes
    and the Phase-17 CI modes stay in lockstep. ``full``, ``nightly``,
    and ``release`` carry no tag filter — they run every spec.
    """

    if mode == "fast":
        return "@p0"
    if mode == "standard":
        return "@p0|@p1"
    return None


def mode_plan(mode: CiMode, *, config: RootConfig) -> ModePlan:
    """Return the :class:`ModePlan` for ``mode`` against the live ``config``.

    Each branch is a tiny, explicit recipe — easy to read end-to-end
    when reviewing PRD §21.3 changes.
    """

    if mode not in CI_MODES:
        raise InvalidCiModeError(mode=str(mode))

    if mode == "fast":
        # Smoke + impacted: functional@p0 + security headers as the cheap
        # required gate. Diff-aware (Phase 17.05) augments the module
        # set when impacted modules are detected.
        requested = ("functional", "security")
        return ModePlan(
            mode=mode,
            modules=_intersect_with_config(requested, config.modules),
            grep=grep_for_mode(mode),
        )

    if mode == "standard":
        # Default for every PR: functional + security + a11y at @p0|@p1.
        requested = ("functional", "security", "accessibility")
        return ModePlan(
            mode=mode,
            modules=_intersect_with_config(requested, config.modules),
            grep=grep_for_mode(mode),
        )

    if mode == "full":
        # Full regression: every module the user enabled. No tag filter.
        return ModePlan(
            mode=mode,
            modules=_modules_from_config(config.modules),
            grep=None,
        )

    if mode == "nightly":
        # Full + chaos + extended security. Chaos is force-enabled even
        # if config has it off — that's the point of nightly.
        modules = list(_modules_from_config(config.modules))
        if "chaos" not in modules:
            modules.append("chaos")
        return ModePlan(
            mode=mode,
            modules=tuple(modules),
            grep=None,
            extras={"extended_security": True},
        )

    # release
    modules = list(_modules_from_config(config.modules))
    if "chaos" not in modules:
        modules.append("chaos")
    current_floor = config.policy.min_quality_score
    overrides: dict[str, int | float | bool] = {}
    if current_floor < _RELEASE_MIN_QUALITY_SCORE:
        overrides["min_quality_score"] = _RELEASE_MIN_QUALITY_SCORE
    return ModePlan(
        mode=mode,
        modules=tuple(modules),
        grep=None,
        policy_overrides=overrides,
    )


# ---------------------------------------------------------------------------
# apply_mode — build the effective config
# ---------------------------------------------------------------------------


def apply_mode(
    config: RootConfig,
    *,
    mode: CiMode,
    fail_under: int | None = None,
) -> tuple[RootConfig, ModePlan]:
    """Return ``(effective_config, plan)`` for ``mode``.

    - ``fail_under`` always wins over the mode's policy override
      (matches PRD §21.1 ``fail-under`` semantics — the user-supplied
      override is authoritative).
    - The returned config has the policy fields updated; module toggles
      are NOT mutated because the lifecycle accepts an explicit
      ``requested_modules`` list which is the authoritative gate.
    """

    if mode not in CI_MODES:
        raise InvalidCiModeError(mode=str(mode))

    plan = mode_plan(mode, config=config)

    new_policy_fields: dict[str, int | float | bool] = dict(plan.policy_overrides)
    if fail_under is not None:
        new_policy_fields["min_quality_score"] = int(fail_under)

    if not new_policy_fields:
        return config, plan

    updated_policy: PolicyConfig = config.policy.model_copy(update=new_policy_fields)
    return config.model_copy(update={"policy": updated_policy}), plan


__all__ = [
    "CI_MODES",
    "DEFAULT_CI_MODE",
    "CiMode",
    "InvalidCiModeError",
    "ModePlan",
    "apply_mode",
    "enabled_modules",
    "grep_for_mode",
    "mode_plan",
]
