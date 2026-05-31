"""Phase 34.01 — SC 2.5.8 Target Size (Minimum)."""

from __future__ import annotations

from modules.accessibility.checks.wcag22 import (
    BoundingBox,
    ClickableElement,
    detect_target_size,
)


def test_target_size_fires_for_20x20_button() -> None:
    clickables = (
        ClickableElement(
            selector="button.icon",
            box=BoundingBox(x=10, y=10, width=20, height=20),
            tag="button",
        ),
    )
    issues = detect_target_size(clickables)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "target-size-min"
    assert issue.success_criterion == "2.5.8"
    assert issue.selector == "button.icon"
    assert "24x24 CSS px" in issue.description
    assert "20" in issue.description


def test_target_size_silent_for_24x24_button() -> None:
    clickables = (
        ClickableElement(
            selector="button.icon",
            box=BoundingBox(x=10, y=10, width=24, height=24),
            tag="button",
        ),
    )
    assert detect_target_size(clickables) == ()


def test_target_size_silent_for_inline_link_exception() -> None:
    clickables = (
        ClickableElement(
            selector="p > a.read-more",
            box=BoundingBox(x=10, y=10, width=20, height=16),
            tag="a",
            inline=True,
        ),
    )
    assert detect_target_size(clickables) == ()


def test_target_size_silent_for_user_agent_default() -> None:
    clickables = (
        ClickableElement(
            selector='input[type="checkbox"]',
            box=BoundingBox(x=10, y=10, width=13, height=13),
            tag="input",
            user_agent_default=True,
        ),
    )
    assert detect_target_size(clickables) == ()


def test_target_size_ignores_zero_box() -> None:
    clickables = (
        ClickableElement(
            selector="button.hidden",
            box=BoundingBox(x=0, y=0, width=0, height=0),
            tag="button",
        ),
    )
    assert detect_target_size(clickables) == ()


def test_target_size_respects_custom_minimum() -> None:
    clickables = (
        ClickableElement(
            selector="button.tap",
            box=BoundingBox(x=10, y=10, width=40, height=40),
            tag="button",
        ),
    )
    issues = detect_target_size(clickables, minimum_px=44)
    assert len(issues) == 1
    assert "44x44" in issues[0].description
