"""Phase 34.01 — SC 2.4.11 Focus Not Obscured (Minimum)."""

from __future__ import annotations

from modules.accessibility.checks.wcag22 import (
    BoundingBox,
    FocusableElement,
    StickyOverlay,
    detect_focus_obscured,
)


def test_focus_obscured_fires_when_sticky_header_overlaps_input() -> None:
    focusables = (
        FocusableElement(
            selector="#email",
            box=BoundingBox(x=20, y=50, width=300, height=32),
        ),
    )
    overlays = (
        StickyOverlay(
            selector="header.sticky",
            box=BoundingBox(x=0, y=0, width=1280, height=80),
        ),
    )
    issues = detect_focus_obscured(focusables, overlays)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "focus-obscured"
    assert issue.success_criterion == "2.4.11"
    assert issue.selector == "#email"
    assert "header.sticky" in issue.description
    assert "Automated WCAG 2.2 check found" in issue.description


def test_focus_obscured_silent_when_input_below_sticky_header() -> None:
    focusables = (
        FocusableElement(
            selector="#email",
            box=BoundingBox(x=20, y=120, width=300, height=32),
        ),
    )
    overlays = (
        StickyOverlay(
            selector="header.sticky",
            box=BoundingBox(x=0, y=0, width=1280, height=80),
        ),
    )
    assert detect_focus_obscured(focusables, overlays) == ()


def test_focus_obscured_ignores_self_overlap() -> None:
    focusables = (
        FocusableElement(
            selector="header.sticky",
            box=BoundingBox(x=0, y=0, width=1280, height=80),
        ),
    )
    overlays = (
        StickyOverlay(
            selector="header.sticky",
            box=BoundingBox(x=0, y=0, width=1280, height=80),
        ),
    )
    assert detect_focus_obscured(focusables, overlays) == ()


def test_focus_obscured_fires_once_when_multiple_overlays_match() -> None:
    focusables = (
        FocusableElement(
            selector="#email",
            box=BoundingBox(x=20, y=50, width=300, height=32),
        ),
    )
    overlays = (
        StickyOverlay(
            selector="header.sticky",
            box=BoundingBox(x=0, y=0, width=1280, height=80),
        ),
        StickyOverlay(
            selector="div.banner",
            box=BoundingBox(x=0, y=0, width=1280, height=120),
        ),
    )
    issues = detect_focus_obscured(focusables, overlays)
    assert len(issues) == 1
    # First overlap wins; we don't double-report.
    assert "header.sticky" in issues[0].description


def test_focus_obscured_silent_when_overlay_zero_height() -> None:
    focusables = (
        FocusableElement(
            selector="#email",
            box=BoundingBox(x=20, y=50, width=300, height=32),
        ),
    )
    overlays = (
        StickyOverlay(
            selector="header.sticky",
            box=BoundingBox(x=0, y=0, width=1280, height=0),
        ),
    )
    assert detect_focus_obscured(focusables, overlays) == ()
