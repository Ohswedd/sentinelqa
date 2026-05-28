"""Integration tests for the landmark structure check (Phase 11.04)."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.accessibility.checks.landmarks import (
    detect_landmark_issues,
    normalise_landmark_issues,
)
from modules.accessibility.findings import findings_from_page
from modules.accessibility.models import A11yPageResult, LandmarkIssue


def _page(*issues: LandmarkIssue) -> A11yPageResult:
    return A11yPageResult(
        route="/dashboard",
        url="http://localhost:3000/dashboard",
        fetched_at="2026-05-28T00:00:00+00:00",
        landmark_issues=tuple(issues),
        duration_ms=10,
    )


def test_fully_compliant_landmarks_yield_no_issues() -> None:
    issues = detect_landmark_issues({"main": 1, "header": 1, "nav": 1, "footer": 1})
    assert issues == ()


def test_missing_main_landmark_emits_issue() -> None:
    issues = detect_landmark_issues({"main": 0, "header": 1, "nav": 1, "footer": 1})
    assert len(issues) == 1
    assert issues[0].category == "missing-landmark"
    assert issues[0].landmark == "main"


def test_duplicate_main_landmark_emits_issue() -> None:
    issues = detect_landmark_issues({"main": 2, "header": 1, "nav": 1, "footer": 1})
    assert len(issues) == 1
    assert issues[0].category == "duplicate-landmark"
    assert "2 <main>" in issues[0].description


def test_recommended_landmarks_missing_emit_separate_issues() -> None:
    issues = detect_landmark_issues({"main": 1, "header": 0, "nav": 0, "footer": 0})
    landmarks = {i.landmark for i in issues}
    assert landmarks == {"header", "nav", "footer"}
    assert all(i.category == "missing-landmark" for i in issues)


def test_normalise_landmark_issues_drops_invalid() -> None:
    raw = [
        {
            "category": "missing-landmark",
            "landmark": "main",
            "description": "No <main>",
        },
        {"category": "bogus", "landmark": "main", "description": "x"},
        {"category": "missing-landmark", "landmark": "", "description": "x"},
    ]
    issues = normalise_landmark_issues(raw)
    assert len(issues) == 1
    assert issues[0].landmark == "main"


def test_findings_built_from_landmark_issues() -> None:
    page = _page(
        LandmarkIssue(
            category="missing-landmark",
            landmark="main",
            description="No <main> landmark found on the page.",
        ),
        LandmarkIssue(
            category="duplicate-landmark",
            landmark="main",
            description="Page contains 2 <main> landmarks; exactly one is required.",
        ),
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        now=datetime(2026, 5, 28, tzinfo=UTC),
    )
    severities = [f.severity for f in findings]
    assert severities == ["medium", "low"]
    for finding in findings:
        assert finding.title.startswith("Automated accessibility check found")
        assert finding.recommendation is not None
