"""Pluggable module + lifecycle-phase registries.

Modules and per-phase hooks register themselves via factories so the
canonical lifecycle in :mod:`engine.orchestrator.run_lifecycle` stays
the *only* place the 17 CLAUDE §10 steps are spelled out. Later phases
(05+) call :func:`default_registry.register_module(...)`;
will replace this with an entry-point discovery mechanism.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.orchestrator.run_lifecycle import LifecycleContext


class LifecyclePhase(str, Enum):
    """The 17 phases of CLAUDE §10 (Run Lifecycle)."""

    LOAD_CONFIG = "load_config"
    VALIDATE_CONFIG = "validate_config"
    RESOLVE_TARGET = "resolve_target"
    ENFORCE_SAFETY_POLICY = "enforce_safety_policy"
    CREATE_RUN_ID = "create_run_id"
    CREATE_ARTIFACT_DIRECTORY = "create_artifact_directory"
    SNAPSHOT_CONFIG = "snapshot_config"
    DISCOVER_APP = "discover_app"
    BUILD_EXECUTION_PLAN = "build_execution_plan"
    RUN_MODULES = "run_modules"
    COLLECT_EVIDENCE = "collect_evidence"
    NORMALIZE_FINDINGS = "normalize_findings"
    CALCULATE_QUALITY_SCORE = "calculate_quality_score"
    APPLY_QUALITY_GATES = "apply_quality_gates"
    GENERATE_REPORTS = "generate_reports"
    PERSIST_ARTIFACTS = "persist_artifacts"
    RETURN_EXIT_CODE = "return_deterministic_exit_code"


# Hook signature: receives the live :class:`LifecycleContext` so hooks can
# read AND mutate state in place. Hooks return nothing — any side effects
# are observed on the context the lifecycle owns. This is intentional: the
# alternative (dict-in / dict-out) makes mutation awkward and forces the
# lifecycle to merge results back, which has bitten us in earlier drafts.
PhaseHook = Callable[["LifecycleContext"], None]

# Module factory: builds a module instance from the config.
# leaves the actual interface unspecified — module phases (05+) refine
# it via abstract base classes and override here.
ModuleFactory = Callable[..., Any]


@dataclass
class ModuleRegistry:
    """Holds module factories and per-phase hooks."""

    modules: dict[str, ModuleFactory] = field(default_factory=dict)
    phase_hooks: dict[LifecyclePhase, list[PhaseHook]] = field(default_factory=dict)

    def register_module(self, name: str, factory: ModuleFactory) -> None:
        if name in self.modules:
            raise ValueError(f"Module {name!r} already registered.")
        self.modules[name] = factory

    def register_phase_hook(self, phase: LifecyclePhase, hook: PhaseHook) -> None:
        self.phase_hooks.setdefault(phase, []).append(hook)

    def clear(self) -> None:
        """Test helper: drop everything.

        Also clears the per-hook sentinel flags (``_reporter_hook_registered``,
        ``_scoring_hooks_registered``) so the next ``RunLifecycle``
        constructor re-registers the default hooks. Without this, a
        ``clear()`` between tests strips the hooks from ``phase_hooks``
        but leaves the flags set, and downstream test runs silently lose
        the reporter / scoring pipeline.
        """

        self.modules.clear()
        self.phase_hooks.clear()
        for flag in ("_reporter_hook_registered", "_scoring_hooks_registered"):
            if hasattr(self, flag):
                delattr(self, flag)


_DEFAULT_REGISTRY = ModuleRegistry()


def default_registry() -> ModuleRegistry:
    """Process-wide registry shared by all CLI commands."""

    return _DEFAULT_REGISTRY


__all__ = [
    "LifecyclePhase",
    "ModuleFactory",
    "ModuleRegistry",
    "PhaseHook",
    "default_registry",
]
