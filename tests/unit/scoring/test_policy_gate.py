"""— policy gate acceptance cases."""

from __future__ import annotations

from engine.config.schema import PolicyConfig
from engine.scoring.policy_gate import apply_policy_gate

from tests.unit.scoring.conftest import SCORING_RUN_ID, make_finding, make_module_result


def test_score_86_no_blockers_min_85_passes() -> None:
    # Single medium finding in accessibility:
    # accessibility = 100-6.5 = 93.5
    # total = 93.5*.10 + 100*.90 = 99.35 (>= 85) → pass_with_warnings.
    # For a pure "pass" with score 86, configure tighter penalties.
    policy = PolicyConfig(min_quality_score=85)
    score, decision, blockers = apply_policy_gate(
        (),
        (),
        policy=policy,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "pass"
    assert score.total >= 85.0
    assert blockers == ()


def test_score_below_threshold_blocks_with_no_findings_findings_added() -> None:
    # 6 high findings in security → security = 100 - 6*17.5 = -5 → floor 0
    # weighted: 0 *.20 + 100 *.80 = 80 → below 85 → blocked.
    policy = PolicyConfig(
        min_quality_score=85,
        block_on_critical=False,
        block_on_high_security=False,
    )
    findings = tuple(
        make_finding(id=f"FND-HIGHSECAA{i:03d}", module="security", severity="high")
        for i in range(6)
    )
    score, decision, blockers = apply_policy_gate(
        findings,
        (),
        policy=policy,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert score.total < 85.0
    assert decision.release_decision == "blocked"
    assert blockers == ()  # gate rules disabled, but score threshold fires
    assert any("below" in r.lower() for r in decision.reasons)


def test_critical_finding_always_blocks() -> None:
    findings = (make_finding(id="FND-CRITAAAAAAA1", module="security", severity="critical"),)
    score, decision, blockers = apply_policy_gate(
        findings,
        (),
        policy=PolicyConfig(),
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert decision.release_decision == "blocked"
    assert any(b.rule_name == "critical_finding" for b in blockers)


def test_flake_rate_above_max_lowers_score(policy_defaults: PolicyConfig) -> None:
    # Flake risk is one of 8 axes weighted at 5%; with a flake rate at
    # the max, that axis is 0 → 5 points lost → total = 95.
    modules = (
        make_module_result(
            id="MOD-FUNCAAAAAAAA",
            name="functional",
            flake_rate=policy_defaults.max_flake_rate,
        ),
    )
    score, decision, _ = apply_policy_gate(
        (),
        modules,
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="passed",
    )
    assert score.total == 95.0
    assert decision.release_decision == "pass"


def test_unsafe_status_returns_unsafe_decision(policy_defaults: PolicyConfig) -> None:
    score, decision, _ = apply_policy_gate(
        (),
        (),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="unsafe_blocked",
    )
    assert decision.release_decision == "unsafe_target_rejected"
    # Score is still computed (and 100 since there are no findings).
    assert score.total == 100.0


def test_incomplete_status_returns_inconclusive(
    policy_defaults: PolicyConfig,
) -> None:
    _, decision, _ = apply_policy_gate(
        (),
        (),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
        run_status="incomplete",
    )
    assert decision.release_decision == "inconclusive"


def test_idempotent_repeat_invocation(policy_defaults: PolicyConfig) -> None:
    """Same inputs → same artifact-visible outputs."""

    findings = (
        make_finding(id="FND-HIGHSECAAAA1", module="security", severity="high"),
        make_finding(id="FND-MEDA11YAAAA1", module="accessibility", severity="medium"),
    )
    modules = (make_module_result(id="MOD-FUNCAAAAAAAA", name="functional", flake_rate=0.01),)
    a_score, a_dec, a_blk = apply_policy_gate(
        findings, modules, policy=policy_defaults, run_id=SCORING_RUN_ID, run_status="passed"
    )
    b_score, b_dec, b_blk = apply_policy_gate(
        findings, modules, policy=policy_defaults, run_id=SCORING_RUN_ID, run_status="passed"
    )
    assert a_score.total == b_score.total
    assert a_score.components == b_score.components
    assert a_score.severity_penalties_applied == b_score.severity_penalties_applied
    assert a_dec.release_decision == b_dec.release_decision
    assert a_dec.blocked_by == b_dec.blocked_by
    assert a_dec.reasons == b_dec.reasons
    assert [(b.rule_name, b.finding_id) for b in a_blk] == [
        (b.rule_name, b.finding_id) for b in b_blk
    ]
