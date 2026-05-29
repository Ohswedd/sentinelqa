"""Edge cases for the scoring lifecycle hooks (task 14.04 / 14.07)."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.config.schema import ProjectConfig, RootConfig, TargetConfig
from engine.orchestrator.registry import LifecyclePhase, ModuleRegistry
from engine.scoring.policy_gate import _gate_hook, _score_hook, register_scoring_hooks


@dataclass
class _FakeCtx:
    """Minimal stand-in for LifecycleContext to exercise the hook guards."""

    run_id: str | None
    typed_findings: tuple = ()
    typed_module_results: tuple = ()
    module_outcomes: list = field(default_factory=list)
    typed_score: object | None = None
    typed_policy: object | None = None
    quality_gate_passed: bool = True
    config: RootConfig | None = None


def test_score_hook_skips_when_run_id_missing() -> None:
    ctx = _FakeCtx(run_id=None)
    _score_hook(ctx)  # type: ignore[arg-type]
    assert ctx.typed_score is None
    assert ctx.typed_policy is None


def test_gate_hook_skips_when_policy_missing() -> None:
    ctx = _FakeCtx(run_id="RUN-NOPOLICYAAA1", typed_policy=None)
    _gate_hook(ctx)  # type: ignore[arg-type]
    # Default `quality_gate_passed=True` remains untouched.
    assert ctx.quality_gate_passed is True


def test_register_scoring_hooks_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_scoring_hooks(registry)
    register_scoring_hooks(registry)
    # Each phase should have exactly one scoring hook registered.
    score_hooks = registry.phase_hooks.get(LifecyclePhase.CALCULATE_QUALITY_SCORE, [])
    gate_hooks = registry.phase_hooks.get(LifecyclePhase.APPLY_QUALITY_GATES, [])
    assert len(score_hooks) == 1
    assert len(gate_hooks) == 1


def test_register_scoring_hooks_after_clear_reregisters() -> None:
    registry = ModuleRegistry()
    register_scoring_hooks(registry)
    registry.clear()
    register_scoring_hooks(registry)
    assert len(registry.phase_hooks.get(LifecyclePhase.CALCULATE_QUALITY_SCORE, [])) == 1
    assert len(registry.phase_hooks.get(LifecyclePhase.APPLY_QUALITY_GATES, [])) == 1


def test_score_hook_treats_errored_modules_as_incomplete() -> None:
    """When any module outcome is errored, the decision must be inconclusive."""

    from engine.orchestrator.run_lifecycle import ModuleOutcome

    config = RootConfig(
        project=ProjectConfig(name="hook-fixture"),
        target=TargetConfig(base_url="http://localhost:3000"),
    )
    ctx = _FakeCtx(
        run_id="RUN-HOOKINCOMPLE",
        config=config,
        module_outcomes=[ModuleOutcome(name="functional", status="errored")],
    )
    _score_hook(ctx)  # type: ignore[arg-type]
    assert ctx.typed_policy is not None
    assert ctx.typed_policy.release_decision == "inconclusive"  # type: ignore[attr-defined]
