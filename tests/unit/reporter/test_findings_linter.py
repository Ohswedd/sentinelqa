"""Unit tests for the vague-finding linter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.reporter.findings_linter import (
    BANNED_DESCRIPTION_PHRASES,
    MIN_TITLE_LENGTH,
    first_blocking_warning,
    lint_finding,
    lint_findings,
)


def _finding(
    *,
    title: str = "Session cookie missing HttpOnly attribute",
    description: str = "Session cookie at /login lacks HttpOnly; Set-Cookie header observed.",
    severity: str = "high",
    evidence: tuple[Evidence, ...] = (),
    fid: str = "FND-LINTAAAAAAAA",
) -> Finding:
    return Finding(
        id=fid,
        run_id="RUN-LINTAAAAAAAA",
        module="security",
        category="security/cookies",
        severity=severity,  # type: ignore[arg-type]
        confidence=0.8,
        title=title,
        description=description,
        location=FindingLocation(route="/login"),
        evidence=evidence,
        recommendation="Set HttpOnly.",
        affected_target="https://localhost:8080",
        created_at=datetime(2026, 5, 27, tzinfo=UTC),
    )


def _evidence() -> Evidence:
    return Evidence(
        id="EVD-LINTAAAAAAAA",
        type="network_log",
        path=Path("traces/login.har"),
        redacted=True,
    )


def test_lint_finding_clean_returns_no_warnings() -> None:
    finding = _finding(evidence=(_evidence(),))
    assert lint_finding(finding) == []


def test_lint_finding_too_short_title() -> None:
    finding = _finding(title="Short", evidence=(_evidence(),))
    warnings = lint_finding(finding)
    codes = {w.code for w in warnings}
    assert "L-FND-001" in codes
    assert any(str(MIN_TITLE_LENGTH) in w.message for w in warnings)


def test_lint_finding_vague_description() -> None:
    finding = _finding(
        title="Security finding identified by module",
        description="Security issue found.",
        evidence=(_evidence(),),
    )
    warnings = lint_finding(finding)
    assert any(w.code == "L-FND-002" for w in warnings)


def test_lint_finding_vague_but_specific_description_passes() -> None:
    finding = _finding(
        title="Security finding identified by module",
        description="Security issue found at /api/v1/users — Set-Cookie header missing Secure.",
        evidence=(_evidence(),),
    )
    warnings = lint_finding(finding)
    # L-FND-002 should NOT fire because the description has specifics.
    assert all(w.code != "L-FND-002" for w in warnings)


def test_lint_finding_blocks_when_evidence_missing_at_medium_or_higher() -> None:
    for severity in ("critical", "high", "medium"):
        finding = _finding(severity=severity, evidence=())
        warnings = lint_finding(finding)
        assert any(w.code == "L-FND-004" for w in warnings), severity


def test_lint_finding_allows_no_evidence_for_low_and_info() -> None:
    for severity in ("low", "info"):
        finding = _finding(severity=severity, evidence=())
        warnings = lint_finding(finding)
        assert all(w.code != "L-FND-004" for w in warnings), severity


def test_lint_findings_aggregates() -> None:
    a = _finding(fid="FND-AAAAAAAAAAAA", title="Short", evidence=(_evidence(),))
    b = _finding(fid="FND-BBBBBBBBBBBB", severity="critical", evidence=())
    warnings = lint_findings([a, b])
    code_per_finding = {(w.finding_id, w.code) for w in warnings}
    assert ("FND-AAAAAAAAAAAA", "L-FND-001") in code_per_finding
    assert ("FND-BBBBBBBBBBBB", "L-FND-004") in code_per_finding


def test_first_blocking_warning_only_returns_evidence_violations() -> None:
    a = _finding(fid="FND-AAAAAAAAAAAA", title="Short", evidence=(_evidence(),))
    b = _finding(fid="FND-BBBBBBBBBBBB", severity="critical", evidence=())
    blocker = first_blocking_warning([a, b])
    assert blocker is not None
    assert blocker.code == "L-FND-004"
    assert blocker.finding_id == "FND-BBBBBBBBBBBB"


def test_first_blocking_warning_returns_none_when_clean() -> None:
    a = _finding(evidence=(_evidence(),))
    assert first_blocking_warning([a]) is None


@pytest.mark.parametrize(
    "pattern",
    [
        "Security issue found.",
        "ERROR FOUND in checkout flow.",
        "Something is wrong here.",
    ],
)
def test_banned_phrases_are_recognized(pattern: str) -> None:
    assert any(p.search(pattern) for p in BANNED_DESCRIPTION_PHRASES)
