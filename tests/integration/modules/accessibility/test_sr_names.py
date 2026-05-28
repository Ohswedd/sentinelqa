"""Integration tests for the accessible-name check (Phase 11.04)."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.accessibility.checks.sr_names import (
    ElementSnapshot,
    detect_missing_accessible_names,
    has_accessible_name,
    normalise_accessible_name_issues,
)
from modules.accessibility.findings import findings_from_page
from modules.accessibility.models import A11yPageResult, AccessibleNameIssue


def _page(*issues: AccessibleNameIssue) -> A11yPageResult:
    return A11yPageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        accessible_name_issues=tuple(issues),
        duration_ms=10,
    )


def test_icon_only_button_without_aria_label_is_finding() -> None:
    snapshot = ElementSnapshot(role="button", selector="#icon-btn")
    issues = detect_missing_accessible_names([snapshot])
    assert len(issues) == 1
    assert issues[0].selector == "#icon-btn"


def test_button_with_aria_label_has_accessible_name() -> None:
    snapshot = ElementSnapshot(role="button", selector="#icon-btn", aria_label="Close")
    issues = detect_missing_accessible_names([snapshot])
    assert issues == ()


def test_button_with_label_text_has_accessible_name() -> None:
    snapshot = ElementSnapshot(role="button", selector="#go", label_text="Go!")
    issues = detect_missing_accessible_names([snapshot])
    assert issues == ()


def test_placeholder_is_not_sufficient_for_accessible_name() -> None:
    snapshot = ElementSnapshot(role="textbox", selector="#q", placeholder="Search")
    # Placeholder text disappears on input — not a sufficient name.
    assert not has_accessible_name(snapshot)
    issues = detect_missing_accessible_names([snapshot])
    assert len(issues) == 1


def test_non_interactive_elements_are_ignored() -> None:
    snapshot = ElementSnapshot(role="presentation", selector="div.bg")
    issues = detect_missing_accessible_names([snapshot])
    assert issues == ()


def test_normalise_accessible_name_issues_drops_invalid() -> None:
    raw = [
        {"selector": "#a", "role": "button", "description": "no name"},
        {"selector": "", "role": "button", "description": "no selector"},
        {"selector": "#b", "role": "link", "description": ""},
    ]
    issues = normalise_accessible_name_issues(raw)
    assert tuple(i.selector for i in issues) == ("#a",)


def test_findings_use_accessible_name_recommendation() -> None:
    page = _page(
        AccessibleNameIssue(
            selector="#icon-btn",
            role="button",
            description="Icon button without aria-label",
        )
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        now=datetime(2026, 5, 28, tzinfo=UTC),
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.title.startswith("Automated accessibility check found")
    assert "aria-label" in (finding.recommendation or "")
    assert finding.severity == "medium"
