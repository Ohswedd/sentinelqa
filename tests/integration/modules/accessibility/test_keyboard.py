"""Integration tests for keyboard checks (Phase 11.03).

The TS helper walks the focus order and writes one
:class:`KeyboardIssue` per defect. These tests cover the deterministic
detection rules + the Python-side normaliser.
"""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.accessibility.checks.keyboard import (
    detect_focus_trap,
    normalise_keyboard_issues,
)
from modules.accessibility.findings import findings_from_page
from modules.accessibility.models import A11yPageResult, KeyboardIssue


def _page(*keyboard_issues: KeyboardIssue) -> A11yPageResult:
    return A11yPageResult(
        route="/dashboard",
        url="http://localhost:3000/dashboard",
        fetched_at="2026-05-28T00:00:00+00:00",
        keyboard_issues=tuple(keyboard_issues),
        duration_ms=10,
    )


def test_modal_without_focus_trap_emits_finding() -> None:
    issue = detect_focus_trap(focusables=3, can_escape_modal=False, inside_modal=True)
    assert issue is not None
    assert issue.category == "focus-trap"


def test_compliant_modal_emits_no_finding() -> None:
    issue = detect_focus_trap(focusables=3, can_escape_modal=True, inside_modal=True)
    assert issue is None


def test_no_modal_open_yields_no_finding() -> None:
    issue = detect_focus_trap(focusables=3, can_escape_modal=False, inside_modal=False)
    assert issue is None


def test_normalise_drops_unknown_categories() -> None:
    raw = [
        {"category": "focus-trap", "description": "Modal blocks focus", "selector": ".modal"},
        {"category": "nonsense", "description": "Should be skipped", "selector": "x"},
        {"category": "focus-visible", "description": "", "selector": "y"},  # empty desc → drop
    ]
    issues = normalise_keyboard_issues(raw)
    assert tuple(i.category for i in issues) == ("focus-trap",)


def test_findings_use_keyboard_recommendations() -> None:
    page = _page(
        KeyboardIssue(
            category="focus-trap",
            selector=".modal",
            description="Tab cannot escape modal",
        ),
        KeyboardIssue(
            category="focus-visible",
            selector="button.icon",
            description="Button has no visible focus state",
        ),
        KeyboardIssue(
            category="keyboard-navigation",
            selector="div.skip",
            description="Element is unreachable via keyboard",
        ),
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        now=datetime(2026, 5, 28, tzinfo=UTC),
    )
    severities = {f.category: f.severity for f in findings}
    assert severities["a11y.focus-trap"] == "high"
    assert severities["a11y.focus-visible"] == "medium"
    assert severities["a11y.keyboard-navigation"] == "medium"
    for finding in findings:
        assert finding.title.startswith("Automated accessibility check found")
        assert "WCAG compliant" not in finding.description
        assert finding.recommendation is not None
