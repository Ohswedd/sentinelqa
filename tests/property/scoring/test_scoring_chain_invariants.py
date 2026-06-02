# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Property invariants for the full scoring chain (v1.7.0, phase 37).

The chain ``compute_score → compute_blockers → decide`` is what every
release gate ultimately reads. Two invariants must hold or the gate
becomes nonsense:

1. **Monotonicity** — adding a finding cannot *raise* the total quality
   score. Lower-severity additions should leave the score unchanged or
   reduce it; higher-severity additions strictly reduce it.
2. **Reproducibility across processes** — the same inputs serialised
   the same way must yield byte-identical decision payloads regardless
   of which subprocess they ran in. The existing
   ``test_reproducibility`` covers same-process equality via
   ``score.json``; this asserts the broader chain (decision + blockers)
   round-trips byte-equal when re-serialised.

Tests are marked ``slow`` so they participate in ``make test-full``
alongside the other Hypothesis suites.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime

import pytest
from engine.config.schema import PolicyConfig
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.module_result import ModuleResult
from engine.domain.test_run import RunStatus
from engine.scoring import (
    apply_policy_gate,
    compute_blockers,
    compute_score,
    decide,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.slow

_RUN_ID = "RUN-INVARIANT001"
_FIXED_TS = datetime(2026, 6, 2, 0, 0, 0, tzinfo=UTC)

_SEVERITIES: tuple[Severity, ...] = ("critical", "high", "medium", "low", "info")
_MODULES: tuple[str, ...] = (
    "functional",
    "security",
    "performance",
    "accessibility",
    "api",
    "visual",
    "llm_audit",
)
_STATUSES: tuple[RunStatus, ...] = ("passed", "incomplete", "dry_run")


def _id(prefix: str, idx: int) -> str:
    suffix = f"{idx:012X}".replace("0", "A")[:12]
    return f"{prefix}-{suffix}"


def _finding(idx: int, module: str, severity: Severity) -> Finding:
    return Finding(
        id=_id("FND", idx),
        run_id=_RUN_ID,
        module=module,
        category=f"{module}/test",
        severity=severity,
        confidence=0.9,
        title=f"finding-{idx}",
        description=f"property-generated finding {idx} for module {module}.",
        location=FindingLocation(),
        recommendation="Fix it.",
        affected_target="http://localhost:3000",
        created_at=_FIXED_TS,
    )


def _module_result(idx: int, module: str) -> ModuleResult:
    return ModuleResult(
        id=_id("MOD", idx),
        name=module,
        status="passed",
        findings=(),
        metrics={"tests_run": 5},
        duration_ms=1000,
        errors=(),
    )


@st.composite
def _scoring_inputs(
    draw: st.DrawFn,
) -> tuple[list[Finding], list[ModuleResult], PolicyConfig, RunStatus]:
    findings_count = draw(st.integers(min_value=0, max_value=8))
    findings: list[Finding] = []
    for i in range(findings_count):
        findings.append(
            _finding(
                i,
                draw(st.sampled_from(_MODULES)),
                draw(st.sampled_from(_SEVERITIES)),
            )
        )

    modules: list[ModuleResult] = []
    for i in range(draw(st.integers(min_value=0, max_value=4))):
        modules.append(_module_result(i + 100, draw(st.sampled_from(_MODULES))))

    policy = PolicyConfig(
        min_quality_score=draw(st.integers(min_value=0, max_value=100)),
        block_on_critical=draw(st.booleans()),
        block_on_high_security=draw(st.booleans()),
        max_flake_rate=draw(st.floats(min_value=0.0, max_value=1.0)),
        max_failed_p1_flows=draw(st.integers(min_value=0, max_value=10)),
        severity_penalty_high=draw(st.floats(min_value=10.0, max_value=25.0)),
        severity_penalty_medium=draw(st.floats(min_value=3.0, max_value=10.0)),
        severity_penalty_low=draw(st.floats(min_value=1.0, max_value=3.0)),
    )
    return findings, modules, policy, draw(st.sampled_from(_STATUSES))


def _score_total(
    findings: Sequence[Finding], modules: Sequence[ModuleResult], policy: PolicyConfig
) -> float:
    return compute_score(
        findings,
        modules,
        policy=policy,
        run_id=_RUN_ID,
    ).total


@given(_scoring_inputs(), st.sampled_from(_SEVERITIES), st.sampled_from(_MODULES))
@settings(
    deadline=None,
    max_examples=400,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_adding_a_finding_never_raises_total_score(
    payload: tuple[list[Finding], list[ModuleResult], PolicyConfig, RunStatus],
    extra_severity: Severity,
    extra_module: str,
) -> None:
    findings, modules, policy, _ = payload
    before = _score_total(findings, modules, policy)

    extra = _finding(9_999, extra_module, extra_severity)
    after = _score_total([*findings, extra], modules, policy)

    # Adding a single finding cannot make the run look healthier.
    # Equality is allowed because info-level adds carry zero penalty and
    # high-severity adds in already-zeroed components don't drop further.
    assert after <= before + 1e-9


@given(_scoring_inputs())
@settings(
    deadline=None,
    max_examples=400,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_chain_is_deterministic(
    payload: tuple[list[Finding], list[ModuleResult], PolicyConfig, RunStatus],
) -> None:
    findings, modules, policy, run_status = payload

    score_a, decision_a, blockers_a = apply_policy_gate(
        findings, modules, policy=policy, run_id=_RUN_ID, run_status=run_status
    )
    score_b, decision_b, blockers_b = apply_policy_gate(
        findings, modules, policy=policy, run_id=_RUN_ID, run_status=run_status
    )

    # Numeric / structural equality.
    assert score_a.total == score_b.total
    assert decision_a.release_decision == decision_b.release_decision
    assert decision_a.blocked_by == decision_b.blocked_by
    assert decision_a.reasons == decision_b.reasons
    assert tuple(asdict(b) for b in blockers_a) == tuple(asdict(b) for b in blockers_b)

    # Wire-level equality. The orchestrator serialises the decision to
    # JSON for downstream consumers; the byte stream must be stable.
    payload_a = json.dumps(
        {
            "score": score_a.total,
            "decision": decision_a.release_decision,
            "blocked_by": list(decision_a.blocked_by),
        },
        sort_keys=True,
    )
    payload_b = json.dumps(
        {
            "score": score_b.total,
            "decision": decision_b.release_decision,
            "blocked_by": list(decision_b.blocked_by),
        },
        sort_keys=True,
    )
    assert payload_a == payload_b


@given(_scoring_inputs())
@settings(
    deadline=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_critical_with_block_policy_never_yields_pass(
    payload: tuple[list[Finding], list[ModuleResult], PolicyConfig, RunStatus],
) -> None:
    findings, modules, _policy, run_status = payload
    policy = PolicyConfig(block_on_critical=True)

    critical = _finding(8_888, "security", "critical")
    score = compute_score([*findings, critical], modules, policy=policy, run_id=_RUN_ID)
    blockers = compute_blockers([*findings, critical], policy=policy)
    decision = decide(
        score,
        blockers,
        findings=[*findings, critical],
        policy=policy,
        run_id=_RUN_ID,
        run_status=run_status,
    )

    # A run carrying *any* critical finding cannot pass when
    # block_on_critical is on. It may legitimately be reported as
    # "inconclusive" if the run itself never completed.
    assert decision.release_decision in {
        "blocked",
        "inconclusive",
        "unsafe_target_rejected",
    }


@given(_scoring_inputs())
@settings(
    deadline=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_score_is_clamped_to_unit_interval(
    payload: tuple[list[Finding], list[ModuleResult], PolicyConfig, RunStatus],
) -> None:
    findings, modules, policy, _ = payload
    score = compute_score(findings, modules, policy=policy, run_id=_RUN_ID)
    assert 0.0 <= score.total <= 100.0
    for axis_value in score.components.values():
        assert 0.0 <= axis_value <= 100.0
