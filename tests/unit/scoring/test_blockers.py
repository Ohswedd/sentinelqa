"""— blocker computation."""

from __future__ import annotations

from engine.config.schema import PolicyConfig
from engine.scoring.blockers import compute_blockers

from tests.unit.scoring.conftest import make_finding


def test_no_findings_no_blockers(policy_defaults: PolicyConfig) -> None:
    assert compute_blockers((), policy=policy_defaults) == []


def test_critical_finding_blocks_by_default(policy_defaults: PolicyConfig) -> None:
    findings = (make_finding(id="FND-CRITAAAAAAA1", module="security", severity="critical"),)
    blockers = compute_blockers(findings, policy=policy_defaults)
    assert len(blockers) == 1
    assert blockers[0].rule_name == "critical_finding"
    assert blockers[0].finding_id == "FND-CRITAAAAAAA1"
    assert "policy.block_on_critical=true" in blockers[0].justification


def test_critical_finding_does_not_block_when_policy_disabled() -> None:
    policy = PolicyConfig(block_on_critical=False)
    findings = (make_finding(id="FND-CRITAAAAAAA1", module="security", severity="critical"),)
    blockers = compute_blockers(findings, policy=policy)
    assert blockers == []


def test_high_security_finding_blocks_by_default(policy_defaults: PolicyConfig) -> None:
    findings = (make_finding(id="FND-HIGHSECAAAA1", module="security", severity="high"),)
    blockers = compute_blockers(findings, policy=policy_defaults)
    assert len(blockers) == 1
    assert blockers[0].rule_name == "security_high"
    assert blockers[0].finding_id == "FND-HIGHSECAAAA1"


def test_high_security_finding_does_not_block_when_policy_disabled() -> None:
    policy = PolicyConfig(block_on_high_security=False)
    findings = (make_finding(id="FND-HIGHSECAAAA1", module="security", severity="high"),)
    assert compute_blockers(findings, policy=policy) == []


def test_high_in_other_modules_does_not_trigger_security_rule(
    policy_defaults: PolicyConfig,
) -> None:
    findings = (
        make_finding(id="FND-HIGHAPIAAAA1", module="api", severity="high"),
        make_finding(id="FND-HIGHFUNAAA1", module="functional", severity="high"),
    )
    blockers = compute_blockers(findings, policy=policy_defaults)
    assert blockers == []


def test_p0_functional_failure_blocks(policy_defaults: PolicyConfig) -> None:
    findings = (
        make_finding(
            id="FND-P0LOGINAAAA1",
            module="functional",
            severity="high",
            title="@p0 @module:functional login flow",
        ),
    )
    blockers = compute_blockers(findings, policy=policy_defaults)
    rules = [b.rule_name for b in blockers]
    assert "p0_flow_failed" in rules


def test_p0_failure_blocks_even_in_p1_lenient_policy() -> None:
    policy = PolicyConfig(max_failed_p1_flows=99)
    findings = (
        make_finding(
            id="FND-P0LOGINAAAA1",
            module="functional",
            severity="high",
            title="@p0 login flow",
        ),
    )
    blockers = compute_blockers(findings, policy=policy)
    assert any(b.rule_name == "p0_flow_failed" for b in blockers)


def test_p1_failure_count_threshold(policy_defaults: PolicyConfig) -> None:
    # Default policy: max_failed_p1_flows=0, so any P1 failure triggers.
    findings = (
        make_finding(
            id="FND-P1FLOWAAAA01",
            module="functional",
            severity="high",
            title="@p1 search flow",
        ),
    )
    blockers = compute_blockers(findings, policy=policy_defaults)
    assert any(b.rule_name == "too_many_p1_failures" for b in blockers)


def test_p1_below_threshold_does_not_block() -> None:
    policy = PolicyConfig(max_failed_p1_flows=3)
    findings = tuple(
        make_finding(
            id=f"FND-P1FLOWAAAA{i:02d}",
            module="functional",
            severity="high",
            title=f"@p1 search flow {i}",
        )
        for i in range(3)
    )
    blockers = [
        b
        for b in compute_blockers(findings, policy=policy)
        if b.rule_name == "too_many_p1_failures"
    ]
    assert blockers == []


def test_p1_above_threshold_blocks_with_structural_rule() -> None:
    policy = PolicyConfig(max_failed_p1_flows=1)
    findings = tuple(
        make_finding(
            id=f"FND-P1FLOWAAAA{i:02d}",
            module="functional",
            severity="high",
            title=f"@p1 search flow {i}",
        )
        for i in range(3)
    )
    blockers = [
        b
        for b in compute_blockers(findings, policy=policy)
        if b.rule_name == "too_many_p1_failures"
    ]
    assert len(blockers) == 1
    assert blockers[0].finding_id is None  # structural rule, no single finding
    assert "max_failed_p1_flows=1" in blockers[0].justification


def test_blocker_output_is_deterministic_across_input_order(
    policy_defaults: PolicyConfig,
) -> None:
    findings_a = (
        make_finding(id="FND-CRITAAAAAAA2", module="security", severity="critical"),
        make_finding(id="FND-CRITAAAAAAA1", module="security", severity="critical"),
    )
    findings_b = tuple(reversed(findings_a))
    out_a = compute_blockers(findings_a, policy=policy_defaults)
    out_b = compute_blockers(findings_b, policy=policy_defaults)
    assert [(b.rule_name, b.finding_id) for b in out_a] == [
        (b.rule_name, b.finding_id) for b in out_b
    ]


def test_multiple_rules_can_fire_for_one_finding(
    policy_defaults: PolicyConfig,
) -> None:
    # A critical security finding hits both critical_finding AND
    # (because severity is critical, not high) only the critical rule.
    # Verify both rules surface independently when they apply.
    findings = (
        make_finding(id="FND-CRITAAAAAAA1", module="security", severity="critical"),
        make_finding(id="FND-HIGHSECAAAA1", module="security", severity="high"),
    )
    blockers = compute_blockers(findings, policy=policy_defaults)
    rules = sorted(b.rule_name for b in blockers)
    assert rules == ["critical_finding", "security_high"]
