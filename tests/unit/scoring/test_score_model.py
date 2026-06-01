"""— exhaustive cases for the scoring model."""

from __future__ import annotations

import pytest
from engine.config.schema import PolicyConfig
from engine.scoring.model import (
    COMPONENT_AXES,
    CRITICAL_PENALTY,
    DEFAULT_WEIGHTS,
    PenaltyTable,
    compute_score,
    derive_penalty_table,
    finding_priority,
)

from tests.unit.scoring.conftest import (
    SCORING_RUN_ID,
    make_finding,
    make_module_result,
)


def test_default_weights_sum_to_one() -> None:
    total = sum(DEFAULT_WEIGHTS[axis] for axis in COMPONENT_AXES)
    # Float-safe equality.
    assert round(total, 6) == 1.0


def test_default_weights_match_prd_19_1() -> None:
    # our product spec1: functional 30, security 20, performance 15,
    # accessibility 10, api 10, visual 5, llm_audit 5, flake_risk 5.
    assert DEFAULT_WEIGHTS["functional"] == 0.30
    assert DEFAULT_WEIGHTS["security"] == 0.20
    assert DEFAULT_WEIGHTS["performance"] == 0.15
    assert DEFAULT_WEIGHTS["accessibility"] == 0.10
    assert DEFAULT_WEIGHTS["api"] == 0.10
    assert DEFAULT_WEIGHTS["visual"] == 0.05
    assert DEFAULT_WEIGHTS["llm_audit"] == 0.05
    assert DEFAULT_WEIGHTS["flake_risk"] == 0.05


def test_derive_penalty_table_uses_policy_defaults() -> None:
    table = derive_penalty_table(PolicyConfig())
    assert table == PenaltyTable(critical=CRITICAL_PENALTY, high=17.5, medium=6.5, low=2.0)


def test_derive_penalty_table_honors_overrides() -> None:
    policy = PolicyConfig(
        severity_penalty_high=20.0,
        severity_penalty_medium=8.0,
        severity_penalty_low=3.0,
    )
    table = derive_penalty_table(policy)
    assert table.high == 20.0
    assert table.medium == 8.0
    assert table.low == 3.0
    # Critical is always CRITICAL_PENALTY (fixed).
    assert table.critical == CRITICAL_PENALTY


def test_penalty_range_is_clamped_by_policy_schema() -> None:
    with pytest.raises(ValueError):
        PolicyConfig(severity_penalty_high=5.0)  # below the 10..25 range
    with pytest.raises(ValueError):
        PolicyConfig(severity_penalty_medium=30.0)  # above the 3..10 range
    with pytest.raises(ValueError):
        PolicyConfig(severity_penalty_low=0.5)  # below the 1..3 range


def test_compute_score_clean_run_is_100(
    policy_defaults: PolicyConfig,
) -> None:
    score = compute_score(
        (),
        (
            make_module_result(id="MOD-FUNCAAAAAAAA", name="functional"),
            make_module_result(id="MOD-SECAAAAAAAAA", name="security"),
        ),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    assert score.total == 100.0
    for axis in COMPONENT_AXES:
        assert score.components[axis] == 100.0


def test_compute_score_one_high_security_finding(
    policy_defaults: PolicyConfig,
) -> None:
    findings = (make_finding(id="FND-SECHIGH00001", module="security", severity="high"),)
    score = compute_score(
        findings,
        (make_module_result(id="MOD-SECAAAAAAAAA", name="security"),),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    # security component: 100 - 17.5 = 82.5
    assert score.components["security"] == 82.5
    # other axes stay at 100.
    assert score.components["functional"] == 100.0
    # severity_penalties_applied bookkeeping:
    assert score.severity_penalties_applied["high"] == 17.5
    assert score.severity_penalties_applied["medium"] == 0.0
    # total = (100*.30) + (82.5*.20) + (100*.15) + (100*.10) +
    # (100*.10) + (100*.05) + (100*.05) + (100*.05) = 96.5
    assert score.total == 96.5


def test_compute_score_two_mediums_in_accessibility(
    policy_defaults: PolicyConfig,
) -> None:
    findings = (
        make_finding(id="FND-A11YMED00001", module="accessibility", severity="medium"),
        make_finding(id="FND-A11YMED00002", module="accessibility", severity="medium"),
    )
    score = compute_score(
        findings,
        (),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    # accessibility component = 100 - 6.5 - 6.5 = 87.0
    assert score.components["accessibility"] == 87.0
    # 100 - 1.3 (penalty contribution from accessibility *.10) = 98.7
    assert score.total == 98.7


def test_component_score_floors_at_zero(
    policy_defaults: PolicyConfig,
) -> None:
    # 10 critical findings in functional → 10 * 30 = 300 → floor 0.
    findings = tuple(
        make_finding(
            id=f"FND-CRITAAAAA{i:03d}",
            module="functional",
            severity="critical",
        )
        for i in range(10)
    )
    score = compute_score(
        findings,
        (make_module_result(id="MOD-FUNCAAAAAAAA", name="functional"),),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    assert score.components["functional"] == 0.0


def test_unknown_module_is_ignored(
    policy_defaults: PolicyConfig,
) -> None:
    """Findings with module names outside COMPONENT_AXES do not lower the score."""

    score = compute_score(
        (make_finding(id="FND-UNKNOWNAAAAA", module="custom_module", severity="critical"),),
        (),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    # Every axis is still 100; the unknown-module finding only affects
    # the severity_penalties_applied bookkeeping.
    for axis in COMPONENT_AXES:
        assert score.components[axis] == 100.0
    assert score.severity_penalties_applied["critical"] == CRITICAL_PENALTY


def test_flake_risk_clean_modules_are_100(
    policy_defaults: PolicyConfig,
) -> None:
    score = compute_score(
        (),
        (
            make_module_result(id="MOD-FUNCAAAAAAAA", name="functional", flake_rate=0.0),
            make_module_result(id="MOD-A11YAAAAAAAA", name="accessibility", flake_rate=0.0),
        ),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    assert score.components["flake_risk"] == 100.0


def test_flake_risk_at_threshold_scores_zero(
    policy_defaults: PolicyConfig,
) -> None:
    score = compute_score(
        (),
        (
            make_module_result(
                id="MOD-FUNCAAAAAAAA",
                name="functional",
                flake_rate=policy_defaults.max_flake_rate,
            ),
        ),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    assert score.components["flake_risk"] == 0.0


def test_flake_risk_above_threshold_is_zero(
    policy_defaults: PolicyConfig,
) -> None:
    score = compute_score(
        (),
        (
            make_module_result(
                id="MOD-FUNCAAAAAAAA",
                name="functional",
                flake_rate=policy_defaults.max_flake_rate * 5,
            ),
        ),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    assert score.components["flake_risk"] == 0.0


def test_flake_risk_no_runner_metrics_defaults_to_100(
    policy_defaults: PolicyConfig,
) -> None:
    score = compute_score(
        (),
        (make_module_result(id="MOD-FUNCAAAAAAAA", name="functional"),),  # no flake_rate metric
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    assert score.components["flake_risk"] == 100.0


def test_flake_risk_handles_zero_threshold() -> None:
    policy = PolicyConfig(max_flake_rate=0.0)
    score_clean = compute_score(
        (),
        (make_module_result(id="MOD-FUNCAAAAAAAA", name="functional", flake_rate=0.0),),
        policy=policy,
        run_id=SCORING_RUN_ID,
    )
    assert score_clean.components["flake_risk"] == 100.0

    score_flaky = compute_score(
        (),
        (make_module_result(id="MOD-FUNCAAAAAAAA", name="functional", flake_rate=0.01),),
        policy=policy,
        run_id=SCORING_RUN_ID,
    )
    assert score_flaky.components["flake_risk"] == 0.0


def test_compute_score_deterministic_with_same_inputs(
    policy_defaults: PolicyConfig,
) -> None:
    findings = (
        make_finding(id="FND-SECHIGH00001", module="security", severity="high"),
        make_finding(id="FND-FUNCMED00001", module="functional", severity="medium"),
    )
    modules = (
        make_module_result(id="MOD-FUNCAAAAAAAA", name="functional", flake_rate=0.01),
        make_module_result(id="MOD-SECAAAAAAAAA", name="security", flake_rate=0.0),
    )
    a = compute_score(findings, modules, policy=policy_defaults, run_id=SCORING_RUN_ID)
    b = compute_score(findings, modules, policy=policy_defaults, run_id=SCORING_RUN_ID)
    # IDs differ (random), but every value persisted to score.json must match.
    assert a.total == b.total
    assert a.components == b.components
    assert a.weights == b.weights
    assert a.severity_penalties_applied == b.severity_penalties_applied


def test_custom_weights_must_cover_all_axes(
    policy_defaults: PolicyConfig,
) -> None:
    bad_weights = dict(DEFAULT_WEIGHTS)
    del bad_weights["flake_risk"]
    with pytest.raises(ValueError):
        compute_score(
            (),
            (),
            policy=policy_defaults,
            run_id=SCORING_RUN_ID,
            weights=bad_weights,
        )


def test_negative_weight_is_rejected(
    policy_defaults: PolicyConfig,
) -> None:
    bad_weights = dict(DEFAULT_WEIGHTS)
    bad_weights["functional"] = -0.1
    with pytest.raises(ValueError):
        compute_score(
            (),
            (),
            policy=policy_defaults,
            run_id=SCORING_RUN_ID,
            weights=bad_weights,
        )


def test_total_is_clamped_to_zero_one_hundred(
    policy_defaults: PolicyConfig,
) -> None:
    # 50 critical findings spread across every weighted axis is enough
    # to floor every component, which floors total at 0.
    findings = tuple(
        make_finding(
            id=f"FND-CRITAAAA{idx:04d}",
            module="functional",
            severity="critical",
        )
        for idx in range(50)
    )
    score = compute_score(
        findings,
        (),
        policy=policy_defaults,
        run_id=SCORING_RUN_ID,
    )
    assert 0.0 <= score.total <= 100.0


def test_finding_priority_reads_title_first() -> None:
    finding = make_finding(
        id="FND-P0TESTAAAAAA",
        module="functional",
        severity="high",
        title="@p0 @module:functional login flow",
        description="some description without a priority tag",
    )
    assert finding_priority(finding) == "p0"


def test_finding_priority_falls_back_to_description() -> None:
    finding = make_finding(
        id="FND-P1TESTAAAAAA",
        module="functional",
        severity="high",
        title="login flow",
        description="Marked @p1 in spec.",
    )
    assert finding_priority(finding) == "p1"


def test_finding_priority_returns_none_when_missing() -> None:
    finding = make_finding(
        id="FND-NOPRIOAAAAAA",
        module="functional",
        severity="high",
        title="login flow",
        description="No tags here.",
    )
    assert finding_priority(finding) is None


def test_finding_priority_is_case_insensitive() -> None:
    finding = make_finding(
        id="FND-P0CAPSAAAAAA",
        module="functional",
        severity="high",
        title="login @P0 flow",
    )
    assert finding_priority(finding) == "p0"
