"""Task 14.05 — scoring reproducibility property tests.

Generates randomized Finding / ModuleResult / PolicyConfig combos and
asserts that two consecutive calls to ``apply_policy_gate`` followed by
``write_score`` produce byte-identical ``score.json`` files. The score
is the most reproducibility-sensitive artifact SentinelQA emits
(CLAUDE.md §25), so this is the canonical drift guard.

Marker: ``slow`` so the test runs under ``make test-full`` (matches the
Phase-03 hypothesis suite layout).
"""

from __future__ import annotations

import json
import string
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.config.schema import PolicyConfig
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.module_result import ModuleResult
from engine.domain.test_run import RunStatus
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.score_writer import write_score
from engine.scoring.policy_gate import apply_policy_gate
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.slow

_RUN_ID = "RUN-PROPSCORE001"
_FIXED_TS = datetime(2026, 5, 28, 9, 0, 0, tzinfo=UTC)

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
    title_pad = string.ascii_letters[idx % len(string.ascii_letters)]
    evidence = ()
    if severity in {"critical", "high", "medium"}:
        evidence = (  # type: ignore[assignment]
            Evidence(
                id=_id("EVD", idx),
                type="source_ref",
                path=Path(f"evidence/{idx}.txt"),
                redacted=True,
            ),
        )
    return Finding(
        id=_id("FND", idx),
        run_id=_RUN_ID,
        module=module,
        category=f"{module}/test",
        severity=severity,
        confidence=0.9,
        title=f"finding {title_pad}{idx}",
        description=f"property-generated finding {idx} for module {module}.",
        location=FindingLocation(),
        evidence=evidence,
        recommendation="Fix it.",
        affected_target="http://localhost:3000",
        created_at=_FIXED_TS,
    )


def _module_result(idx: int, module: str, flake_rate: float | None) -> ModuleResult:
    metrics: dict[str, float | int] = {"tests_run": 5}
    if flake_rate is not None:
        metrics["flake_rate"] = round(flake_rate, 4)
    return ModuleResult(
        id=_id("MOD", idx),
        name=module,
        status="passed",
        findings=(),
        metrics=metrics,
        duration_ms=1000,
        errors=(),
    )


@st.composite
def scoring_inputs(draw):
    finding_count = draw(st.integers(min_value=0, max_value=10))
    findings: list[Finding] = []
    for i in range(finding_count):
        module = draw(st.sampled_from(_MODULES))
        severity = draw(st.sampled_from(_SEVERITIES))
        findings.append(_finding(i, module, severity))

    module_count = draw(st.integers(min_value=0, max_value=6))
    modules: list[ModuleResult] = []
    for i in range(module_count):
        m = draw(st.sampled_from(_MODULES))
        rate = draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=0.5)))
        modules.append(_module_result(i + 100, m, rate))

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
    run_status = draw(st.sampled_from(_STATUSES))
    return findings, modules, policy, run_status


def _emit_score_json(
    findings: Sequence[Finding],
    modules: Sequence[ModuleResult],
    policy: PolicyConfig,
    run_status: RunStatus,
    *,
    workspace: Path,
) -> bytes:
    artifacts = ArtifactDirectory.create(workspace, _RUN_ID)
    score, decision, _ = apply_policy_gate(
        findings,
        modules,
        policy=policy,
        run_id=_RUN_ID,
        run_status=run_status,
    )
    path = write_score(
        artifacts,
        run_id=_RUN_ID,
        score=score,
        policy_decision=decision,
        policy_config=policy.to_dict(),
    )
    return path.read_bytes()


@given(scoring_inputs())
@settings(
    deadline=None,
    max_examples=5000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_score_json_is_byte_identical_for_same_inputs(payload) -> None:
    findings, modules, policy, run_status = payload
    with tempfile.TemporaryDirectory(prefix="sentinelqa-score-a-") as ta:
        bytes_a = _emit_score_json(findings, modules, policy, run_status, workspace=Path(ta))
    with tempfile.TemporaryDirectory(prefix="sentinelqa-score-b-") as tb:
        bytes_b = _emit_score_json(findings, modules, policy, run_status, workspace=Path(tb))
    assert bytes_a == bytes_b
    # JSON-decode equality too, so a future writer change that adds
    # significant whitespace fails before we ship.
    assert json.loads(bytes_a) == json.loads(bytes_b)
