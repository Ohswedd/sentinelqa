"""Token budget enforcement tests."""

from __future__ import annotations

import pytest
from engine.planner.llm_adapter import (
    BudgetExceededError,
    LlmUsage,
    ensure_within_budget,
    estimate_cost_usd,
)


def test_estimate_cost_is_positive() -> None:
    assert estimate_cost_usd(input_tokens=1000, output_tokens=1000) > 0


def test_estimate_cost_zero_when_no_tokens() -> None:
    assert estimate_cost_usd(input_tokens=0, output_tokens=0) == 0.0


def test_budget_check_passes_under_budget() -> None:
    usage = LlmUsage(cost_usd=0.1)
    ensure_within_budget(usage=usage, additional_cost=0.1, budget_usd=0.5)


def test_budget_check_raises_over_budget() -> None:
    usage = LlmUsage(cost_usd=0.4)
    with pytest.raises(BudgetExceededError):
        ensure_within_budget(usage=usage, additional_cost=0.2, budget_usd=0.5)


def test_usage_add_accumulates() -> None:
    usage = LlmUsage()
    updated = usage.add(input_tokens=10, output_tokens=20, cost_usd=0.01)
    assert updated.input_tokens == 10
    assert updated.output_tokens == 20
    assert updated.cost_usd == pytest.approx(0.01)
    assert updated.requests == 1
