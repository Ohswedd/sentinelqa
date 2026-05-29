"""Release-decision logic (task 14.03, PRD §19.3).

Translates the numeric score + blockers + run status into a
:class:`engine.domain.policy_decision.PolicyDecision`. Decision
priority (top wins):

1. ``run_status == "unsafe_blocked"``  → ``unsafe_target_rejected``.
2. ``run_status == "incomplete"``     → ``inconclusive``.
3. ``run_status == "dry_run"``        → ``inconclusive`` (no signal).
4. Any blocker                        → ``blocked``.
5. Score < policy.min_quality_score   → ``blocked``.
6. Any medium severity finding        → ``pass_with_warnings``.
7. Otherwise                          → ``pass``.

The ``reasons`` tuple records each rule that fired so the explain
report (task 14.06) can render an honest narrative.
"""

from __future__ import annotations

from collections.abc import Iterable

from engine.config.schema import PolicyConfig
from engine.domain.finding import Finding
from engine.domain.ids import IdGenerator
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import RunStatus
from engine.scoring.blockers import Blocker


def decide(
    score: QualityScore | None,
    blockers: Iterable[Blocker],
    *,
    findings: Iterable[Finding],
    policy: PolicyConfig,
    run_id: str,
    run_status: RunStatus,
    id_generator: IdGenerator | None = None,
) -> PolicyDecision:
    """Return the canonical :class:`PolicyDecision` for a run."""

    blockers_t = tuple(blockers)
    findings_t = tuple(findings)
    decision, reasons = _select_decision(
        score=score,
        blockers=blockers_t,
        findings=findings_t,
        policy=policy,
        run_status=run_status,
    )
    blocked_by = tuple(b.finding_id for b in blockers_t if b.finding_id is not None)
    return PolicyDecision(
        id=(id_generator or IdGenerator()).new("PD"),
        run_id=run_id,
        release_decision=decision,
        blocked_by=blocked_by,
        reasons=reasons,
    )


def _select_decision(
    *,
    score: QualityScore | None,
    blockers: tuple[Blocker, ...],
    findings: tuple[Finding, ...],
    policy: PolicyConfig,
    run_status: RunStatus,
) -> tuple[ReleaseDecision, tuple[str, ...]]:
    if run_status == "unsafe_blocked":
        return "unsafe_target_rejected", ("Run blocked by safety policy; no audit performed.",)
    if run_status == "incomplete":
        return "inconclusive", (
            "Run did not complete (one or more modules errored). " "Score is not authoritative.",
        )
    if run_status == "dry_run":
        return "inconclusive", ("Dry-run only — execution plan built but no modules ran.",)

    reasons: list[str] = []
    if blockers:
        for b in blockers:
            reasons.append(f"[{b.rule_name}] {b.justification}")
        return "blocked", tuple(reasons)

    threshold = float(policy.min_quality_score)
    if score is not None and score.total < threshold:
        return "blocked", (
            f"Quality score {score.total:.2f} is below the configured "
            f"threshold ({threshold:.2f}).",
        )

    has_medium = any(f.severity == "medium" for f in findings)
    if has_medium:
        return "pass_with_warnings", (
            "Run passed but at least one medium-severity finding was "
            "recorded; review before release.",
        )

    return "pass", ("Run passed all gates with no critical, high, or medium findings.",)


__all__ = ["decide"]
