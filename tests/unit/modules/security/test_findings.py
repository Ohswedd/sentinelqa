"""Findings translation tests (Phase 13)."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.security.findings import findings_from_checks
from modules.security.models import SecurityCheckResult, SecurityIssue


def _issue() -> SecurityIssue:
    return SecurityIssue(
        rule_id="SEC-HEADERS-HSTS-MISSING",
        severity="high",
        confidence=0.9,
        title="HSTS missing",
        description="No HSTS",
        route="/login",
        evidence={"observed": "absent"},
        recommendation="Send HSTS",
    )


def test_issue_to_finding_carries_evidence_and_metadata() -> None:
    result = SecurityCheckResult(
        check="headers",
        targets_scanned=1,
        issues=(_issue(),),
        duration_ms=5,
    )
    findings = findings_from_checks(
        checks=[result],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost/",
        id_generator=IdGenerator(),
        artifact_paths={"headers": "security/headers.json"},
        now=datetime.now(UTC),
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.module == "security"
    assert f.severity == "high"
    assert f.affected_target == "http://localhost/"
    assert f.suggested_fix == "Send HSTS"
    assert str(f.evidence[0].path) == "security/headers.json"
    assert "observed=absent" in f.description


def test_skipped_check_emits_no_findings() -> None:
    result = SecurityCheckResult(
        check="sqli",
        targets_scanned=0,
        issues=(),
        duration_ms=0,
        skipped=True,
        skipped_reason="disabled",
    )
    findings = findings_from_checks(
        checks=[result],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost/",
        id_generator=IdGenerator(),
    )
    assert findings == ()
