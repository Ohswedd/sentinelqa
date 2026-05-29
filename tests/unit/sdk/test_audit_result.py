"""``AuditResult`` derived views, agent-message stream, immutability."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain.finding import Finding, FindingLocation
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore

from sentinelqa import AuditResult
from sentinelqa._models import build_audit_result


def _make_finding(*, severity: str, fid: str, module: str = "security") -> Finding:
    return Finding(
        id=fid,
        run_id="RUN-AAAAAAAAAAAA",
        module=module,
        category=f"{module}/issue",
        severity=severity,  # type: ignore[arg-type]
        confidence=0.9,
        title=f"{severity} finding",
        description=f"{severity} finding description.",
        location=FindingLocation(route="/x"),
        evidence=(),
        recommendation="Fix it.",
        created_at=datetime.now(UTC),
    )


def _make_result(
    *,
    status: str = "passed",
    findings: tuple[Finding, ...] = (),
    decision: str | None = "pass",
    score: float | None = 92.0,
) -> AuditResult:
    started = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)
    finished = datetime(2026, 5, 29, 12, 5, tzinfo=UTC)
    typed_score: QualityScore | None = None
    if score is not None:
        typed_score = QualityScore(
            id="SCR-AAAAAAAAAAAA",
            run_id="RUN-AAAAAAAAAAAA",
            total=score,
        )
    typed_policy: PolicyDecision | None = None
    if decision is not None:
        typed_policy = PolicyDecision(
            id="PD-AAAAAAAAAAAA",
            run_id="RUN-AAAAAAAAAAAA",
            release_decision=decision,  # type: ignore[arg-type]
        )
    return build_audit_result(
        run_id="RUN-AAAAAAAAAAAA",
        status=status,  # type: ignore[arg-type]
        target_url="http://localhost:3000/",
        config_digest="sha256:abc",
        started_at=started,
        finished_at=finished,
        modules_run=("security", "accessibility"),
        typed_findings=findings,
        typed_module_results=(),
        typed_score=typed_score,
        typed_policy=typed_policy,
        run_dir=Path("/runs/RUN-AAAAAAAAAAAA"),
    )


def test_passed_view_true_only_on_clean_pass() -> None:
    assert _make_result(status="passed", decision="pass").passed is True
    assert _make_result(status="passed", decision="pass_with_warnings").passed is True
    assert _make_result(status="failed", decision="blocked").passed is False
    assert _make_result(status="incomplete", decision="inconclusive").passed is False
    assert _make_result(status="unsafe_blocked", decision="unsafe_target_rejected").passed is False


def test_failures_view_includes_critical_and_high() -> None:
    findings = (
        _make_finding(severity="critical", fid="FND-CRITAAAAAAAA"),
        _make_finding(severity="high", fid="FND-HIGHAAAAAAAA"),
        _make_finding(severity="medium", fid="FND-MEDAAAAAAAAA"),
        _make_finding(severity="low", fid="FND-LOWAAAAAAAAA"),
    )
    result = _make_result(findings=findings)
    assert tuple(f.id for f in result.failures) == ("FND-CRITAAAAAAAA", "FND-HIGHAAAAAAAA")


def test_blockers_view_is_critical_only() -> None:
    findings = (
        _make_finding(severity="critical", fid="FND-CRITAAAAAAAA"),
        _make_finding(severity="high", fid="FND-HIGHAAAAAAAA"),
    )
    result = _make_result(findings=findings)
    assert tuple(f.id for f in result.blockers) == ("FND-CRITAAAAAAAA",)


def test_findings_by_severity_filters() -> None:
    findings = (
        _make_finding(severity="high", fid="FND-HIGHAAAAAAAA"),
        _make_finding(severity="medium", fid="FND-MEDAAAAAAAAA"),
    )
    result = _make_result(findings=findings)
    assert tuple(f.id for f in result.findings_by_severity("medium")) == ("FND-MEDAAAAAAAAA",)


def test_findings_by_module_filters() -> None:
    findings = (
        _make_finding(severity="high", fid="FND-HIGHAAAAAAAA", module="security"),
        _make_finding(severity="medium", fid="FND-MEDAAAAAAAAA", module="accessibility"),
    )
    result = _make_result(findings=findings)
    assert tuple(f.id for f in result.findings_by_module("accessibility")) == ("FND-MEDAAAAAAAAA",)


def test_result_is_frozen() -> None:
    from pydantic import ValidationError

    result = _make_result()
    with pytest.raises(ValidationError):
        result.run_id = "RUN-BBBBBBBBBBBB"


def test_release_decision_falls_back_when_no_policy() -> None:
    assert _make_result(status="passed", decision=None).release_decision == "pass"
    assert _make_result(status="dry_run", decision=None).release_decision == "inconclusive"
    assert (
        _make_result(status="unsafe_blocked", decision=None).release_decision
        == "unsafe_target_rejected"
    )
    assert _make_result(status="failed", decision=None).release_decision == "blocked"
    assert _make_result(status="incomplete", decision=None).release_decision == "inconclusive"


def test_quality_score_falls_back_to_none() -> None:
    assert _make_result(score=None).quality_score is None
    assert _make_result(score=87.5).quality_score == 87.5


def test_to_agent_messages_order_is_stable() -> None:
    findings = (
        _make_finding(severity="critical", fid="FND-CRITAAAAAAAA"),
        _make_finding(severity="high", fid="FND-HIGHAAAAAAAA"),
    )
    result = _make_result(findings=findings)
    messages = result.to_agent_messages()
    # Shape: summary -> finding -> finding -> blocker_summary -> next_actions
    assert messages[0]["type"] == "run_summary"
    assert messages[1]["type"] == "finding"
    assert messages[1]["id"] == "FND-CRITAAAAAAAA"
    assert messages[2]["type"] == "finding"
    assert messages[2]["id"] == "FND-HIGHAAAAAAAA"
    assert messages[3]["type"] == "blocker_summary"
    assert messages[4]["type"] == "next_actions"
    assert messages[3]["blocking_count"] == 1
    assert messages[3]["failing_count"] == 2


def test_to_agent_messages_carries_schema_version() -> None:
    result = _make_result()
    summary = result.to_agent_messages()[0]
    assert summary["agent_message_schema_version"]
    assert summary["schema_version"]


def test_next_actions_describes_unsafe_target() -> None:
    result = _make_result(status="unsafe_blocked", decision="unsafe_target_rejected")
    msgs = result.to_agent_messages()
    actions = msgs[-1]["actions"]
    assert any("target.allowed_hosts" in a for a in actions)


def test_next_actions_describes_dry_run() -> None:
    result = _make_result(status="dry_run", decision="inconclusive")
    actions = result.to_agent_messages()[-1]["actions"]
    assert any("--dry-run" in a for a in actions)


def test_next_actions_handles_clean_pass() -> None:
    result = _make_result()
    actions = result.to_agent_messages()[-1]["actions"]
    assert any("No action required" in a for a in actions)


def test_next_actions_describes_blockers() -> None:
    findings = (_make_finding(severity="critical", fid="FND-CRITAAAAAAAA"),)
    result = _make_result(findings=findings)
    actions = result.to_agent_messages()[-1]["actions"]
    assert any("blocking" in a for a in actions)


def test_module_result_round_trips_through_result() -> None:
    mr = ModuleResult(
        id="MOD-AAAAAAAAAAAA",
        name="security",
        status="passed",
        duration_ms=120,
    )
    result = build_audit_result(
        run_id="RUN-AAAAAAAAAAAA",
        status="passed",
        target_url="http://localhost:3000/",
        config_digest="sha256:abc",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        modules_run=("security",),
        typed_findings=(),
        typed_module_results=(mr,),
        typed_score=None,
        typed_policy=None,
        run_dir=Path("/runs/RUN-AAAAAAAAAAAA"),
    )
    assert result.module_results == (mr,)
