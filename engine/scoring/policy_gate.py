"""Policy gate (task 14.04, our engineering rules §39).

Combines :mod:`engine.scoring.model`, :mod:`engine.scoring.blockers`,
and :mod:`engine.scoring.decision` into the canonical lifecycle hooks
the orchestrator registers on step 13 (``calculate_quality_score``)
and step 14 (``apply_quality_gates``).

After ``apply_quality_gates`` runs, the lifecycle's ``_finalize_status``
reads ``ctx.quality_gate_passed`` and stamps ``test_run.status``.
The CLI then maps that status onto the canonical exit-code grid
via :mod:`engine.policy.exit_codes` (the documentation):

- ``passed`` → 0
- ``failed`` → 1
- ``unsafe_blocked`` → 4
- ``incomplete`` → 6
- ``dry_run`` → 0
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from engine.config.schema import PolicyConfig
from engine.domain.finding import Finding
from engine.domain.ids import IdGenerator
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import RunStatus
from engine.scoring.blockers import Blocker, compute_blockers
from engine.scoring.decision import decide
from engine.scoring.model import compute_score

if TYPE_CHECKING:
    from engine.orchestrator.run_lifecycle import LifecycleContext


def apply_policy_gate(
    findings: Iterable[Finding],
    module_results: Iterable[ModuleResult],
    *,
    policy: PolicyConfig,
    run_id: str,
    run_status: RunStatus,
    id_generator: IdGenerator | None = None,
) -> tuple[QualityScore, PolicyDecision, tuple[Blocker, ...]]:
    """Compute the score, blockers, and decision in one call.

    Convenience helper used by the lifecycle hook below and exercised
    directly by the reproducibility test (task 14.05) so the
    end-to-end pipeline is the same path tests + production take.
    """

    findings_t = tuple(findings)
    module_results_t = tuple(module_results)
    id_gen = id_generator or IdGenerator()

    score = compute_score(
        findings_t,
        module_results_t,
        policy=policy,
        run_id=run_id,
        id_generator=id_gen,
    )
    blockers = tuple(compute_blockers(findings_t, policy=policy))
    decision = decide(
        score,
        blockers,
        findings=findings_t,
        policy=policy,
        run_id=run_id,
        run_status=run_status,
        id_generator=id_gen,
    )
    return score, decision, blockers


def register_scoring_hooks(registry: Any) -> None:
    """Wire the score + gate hooks onto the orchestrator registry.

    Idempotent so tests that build fresh lifecycles don't double-register.
    """

    if getattr(registry, "_scoring_hooks_registered", False):
        return
    # Local import to avoid pulling the orchestrator at import time of
    # engine.scoring (which would create a cycle through the reporter).
    from engine.orchestrator.registry import LifecyclePhase

    registry.register_phase_hook(LifecyclePhase.CALCULATE_QUALITY_SCORE, _score_hook)
    registry.register_phase_hook(LifecyclePhase.APPLY_QUALITY_GATES, _gate_hook)
    registry._scoring_hooks_registered = True


def _score_hook(ctx: LifecycleContext) -> None:
    """Compute the score + decision and stash them on the context.

    ``ctx.status`` isn't finalized until :func:`generate_reports`, so we
    derive the *effective* status for the decision from module outcomes:
    any errored module → ``incomplete`` → ``inconclusive``; otherwise
    treat the run as provisionally ``passed``. The lifecycle's later
    ``_finalize_status`` will downgrade to ``failed`` if the gate hook
    flips ``quality_gate_passed``.
    """

    if ctx.run_id is None:
        return
    effective_status: RunStatus = (
        "incomplete" if any(o.status == "errored" for o in ctx.module_outcomes) else "passed"
    )
    score, decision, _ = apply_policy_gate(
        ctx.typed_findings,
        ctx.typed_module_results,
        policy=ctx.config.policy,
        run_id=ctx.run_id,
        run_status=effective_status,
    )
    ctx.typed_score = score
    ctx.typed_policy = decision


def _gate_hook(ctx: LifecycleContext) -> None:
    """Mark the run failed if the release decision is ``blocked``.

    ``inconclusive`` / ``unsafe_target_rejected`` are NOT failures here
    — the lifecycle already stamps those statuses via the safety /
    module-error paths. ``pass`` and ``pass_with_warnings`` leave the
    flag alone.
    """

    decision = ctx.typed_policy
    if decision is None:
        return
    if decision.release_decision == "blocked":
        ctx.quality_gate_passed = False


__all__ = ["apply_policy_gate", "register_scoring_hooks"]
