"""Analyzer ↔ Healer routing tests."""

from __future__ import annotations

import pytest
from engine.analyzer.models import (
    AnalyzerResult,
    FailureClassification,
    RetryDecision,
    RootCauseHypothesis,
)
from engine.analyzer.pipeline import is_healer_candidate


def _result(*, category: str, confidence: float) -> AnalyzerResult:
    return AnalyzerResult(
        test_id="t",
        classification=FailureClassification(
            category=category,  # type: ignore[arg-type]
            confidence=confidence,
            rationale="r",
        ),
        hypothesis=RootCauseHypothesis(
            category=category,  # type: ignore[arg-type]
            hypothesis="h",
            confidence=confidence,
        ),
        retry_decision=RetryDecision(
            decision="no_action",
            reason="r",
            confidence=confidence,
        ),
    )


def test_healer_candidate_for_test_bug_above_threshold() -> None:
    assert is_healer_candidate(_result(category="test_bug", confidence=0.9)) is True


def test_healer_skips_app_bug() -> None:
    assert is_healer_candidate(_result(category="app_bug", confidence=0.99)) is False


def test_healer_skips_environment_failure() -> None:
    assert is_healer_candidate(_result(category="environment_failure", confidence=0.99)) is False


@pytest.mark.parametrize(
    "category",
    [
        "flake",
        "data_setup_failure",
        "auth_failure",
        "api_failure",
        "performance_regression",
        "security_finding",
        "accessibility_violation",
        "unknown",
    ],
)
def test_healer_skips_non_test_bug_categories(category: str) -> None:
    assert is_healer_candidate(_result(category=category, confidence=0.99)) is False


def test_healer_skips_low_confidence_test_bug() -> None:
    assert is_healer_candidate(_result(category="test_bug", confidence=0.4)) is False
