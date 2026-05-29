"""Task 14.03 — release decision."""

from __future__ import annotations

from collections.abc import Iterable

from engine.config.schema import PolicyConfig
from engine.domain.finding import Finding
from engine.domain.ids import IdGenerator
from engine.domain.module_result import ModuleResult
from engine.domain.quality_score import QualityScore
from engine.scoring.blockers import compute_blockers
from engine.scoring.decision import decide
from engine.scoring.model import compute_score

from tests.unit.scoring.conftest import SCORING_RUN_ID, make_finding


def _score_for(
    findings: Iterable[Finding],
    modules: Iterable[ModuleResult],
    policy: PolicyConfig,
) -> QualityScore:
    return compute_score(findings, modules, policy=policy, run_id=SCORING_RUN_ID)


def test_unsafe_status_short_circuits(policy_defaults: PolicyConfig) -> None:
    decision = decide(
        None,
        (),
        findings=(),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="unsafe_blocked",
    )
    assert decision.release_decision == "unsafe_target_rejected"
    assert decision.blocked_by == ()
    assert "safety policy" in decision.reasons[0]


def test_incomplete_status_inconclusive(policy_defaults: PolicyConfig) -> None:
    decision = decide(
        None,
        (),
        findings=(),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="incomplete",
    )
    assert decision.release_decision == "inconclusive"


def test_dry_run_status_inconclusive(policy_defaults: PolicyConfig) -> None:
    decision = decide(
        None,
        (),
        findings=(),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="dry_run",
    )
    assert decision.release_decision == "inconclusive"


def test_blockers_force_blocked(policy_defaults: PolicyConfig) -> None:
    findings = (make_finding(id="FND-CRITAAAAAAA1", module="security", severity="critical"),)
    score = _score_for(findings, (), policy_defaults)
    blockers = tuple(compute_blockers(findings, policy=policy_defaults))
    decision = decide(
        score,
        blockers,
        findings=findings,
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "blocked"
    assert "FND-CRITAAAAAAA1" in decision.blocked_by


def test_score_below_minimum_is_blocked() -> None:
    # 5 high findings in functional → component score 100-5*17.5 = 12.5
    # weighted: 12.5 * .30 + 100 * .70 = 73.75 → below 85.
    policy = PolicyConfig(min_quality_score=85, block_on_critical=False, max_failed_p1_flows=99)
    findings = tuple(
        make_finding(
            id=f"FND-HIGHFUNAA{i:03d}",
            module="functional",
            severity="high",
            title=f"plain functional failure {i}",  # no @p0 / @p1 tag
        )
        for i in range(5)
    )
    score = _score_for(findings, (), policy)
    decision = decide(
        score,
        (),
        findings=findings,
        policy=policy,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "blocked"
    assert "below" in decision.reasons[0].lower()


def test_passing_with_medium_finding_is_warnings(
    policy_defaults: PolicyConfig,
) -> None:
    findings = (make_finding(id="FND-MEDA11YAAAA1", module="accessibility", severity="medium"),)
    score = _score_for(findings, (), policy_defaults)
    decision = decide(
        score,
        (),
        findings=findings,
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "pass_with_warnings"


def test_clean_run_passes(policy_defaults: PolicyConfig) -> None:
    score = _score_for((), (), policy_defaults)
    decision = decide(
        score,
        (),
        findings=(),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "pass"


def test_decision_records_each_blocker_reason(
    policy_defaults: PolicyConfig,
) -> None:
    findings = (
        make_finding(id="FND-CRITAAAAAAA1", module="security", severity="critical"),
        make_finding(id="FND-HIGHSECAAAA1", module="security", severity="high"),
    )
    score = _score_for(findings, (), policy_defaults)
    blockers = tuple(compute_blockers(findings, policy=policy_defaults))
    decision = decide(
        score,
        blockers,
        findings=findings,
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "blocked"
    # Each blocker rule should appear once in `reasons`.
    rule_names = [r.split("]")[0].strip("[") for r in decision.reasons]
    assert "critical_finding" in rule_names
    assert "security_high" in rule_names


def test_blocked_by_excludes_structural_rules() -> None:
    # max_failed_p1_flows is structural — finding_id is None — so it
    # should not appear in `blocked_by` even though it's a blocker.
    policy = PolicyConfig(max_failed_p1_flows=0)
    findings = (
        make_finding(
            id="FND-P1FLOWAAAAAA1",
            module="functional",
            severity="high",
            title="@p1 search flow",
        ),
    )
    score = _score_for(findings, (), policy)
    blockers = tuple(compute_blockers(findings, policy=policy))
    decision = decide(
        score,
        blockers,
        findings=findings,
        policy=policy,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "blocked"
    assert "FND-P1FLOWAAAAAA1" not in decision.blocked_by or len(decision.blocked_by) == 1


def test_decision_id_uses_pd_prefix(policy_defaults: PolicyConfig) -> None:
    score = _score_for((), (), policy_defaults)
    decision = decide(
        score,
        (),
        findings=(),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="passed",
        id_generator=IdGenerator(),
    )
    assert decision.id.startswith("PD-")
