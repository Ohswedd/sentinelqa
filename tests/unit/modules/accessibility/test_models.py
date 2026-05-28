"""Unit tests for the typed accessibility models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.accessibility.models import (
    A11Y_RESULT_SCHEMA_VERSION,
    A11yPageResult,
    A11yRunOutcome,
    AxeNode,
    AxeViolation,
)


def test_schema_version_constant_is_stable() -> None:
    assert A11Y_RESULT_SCHEMA_VERSION == "1"


def test_axe_node_defaults_are_safe() -> None:
    node = AxeNode()
    assert node.target == ()
    assert node.html == ""
    assert node.failure_summary == ""


def test_axe_violation_requires_rule_id_and_impact() -> None:
    with pytest.raises(ValidationError):
        AxeViolation()  # type: ignore[call-arg]


def test_a11y_page_result_round_trip_serialisation() -> None:
    page = A11yPageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        axe_violations=(
            AxeViolation(
                rule_id="image-alt",
                impact="critical",
                tags=("wcag2a",),
                help="Images must have alt",
                help_url="https://example.test/image-alt",
                description="Image without alt",
                nodes=(AxeNode(target=("img",), html="<img>"),),
            ),
        ),
        duration_ms=42,
    )
    dumped = page.model_dump()
    rehydrated = A11yPageResult.model_validate(dumped)
    assert rehydrated == page


def test_a11y_page_result_total_issue_count() -> None:
    page = A11yPageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        axe_violations=(
            AxeViolation(
                rule_id="image-alt",
                impact="critical",
                nodes=(),
            ),
        ),
        duration_ms=10,
    )
    outcome = A11yRunOutcome(pages=(page,), duration_ms=10)
    assert outcome.total_issues == 1
