"""Per-run cost budget enforcement (:class:`engine.llm.LlmBudget`)."""

from __future__ import annotations

import pytest
from engine.errors.base import LlmBudgetExceededError
from engine.llm.budget import (
    BudgetExceededError,
    LlmBudget,
    LlmUsage,
    ensure_within_budget,
    estimate_cost_usd,
)


def test_estimate_cost_usd_uses_default_rates() -> None:
    cost = estimate_cost_usd(input_tokens=1000, output_tokens=1000)
    # 1k * 0.003 + 1k * 0.015 = 0.018
    assert pytest.approx(cost, rel=1e-6) == 0.018


def test_estimate_cost_usd_honors_custom_rates() -> None:
    cost = estimate_cost_usd(
        input_tokens=1000,
        output_tokens=1000,
        price_per_1k_input=0.001,
        price_per_1k_output=0.002,
    )
    assert pytest.approx(cost, rel=1e-6) == 0.003


def test_usage_add_accumulates() -> None:
    usage = LlmUsage()
    usage = usage.add(input_tokens=100, output_tokens=50, cost_usd=0.01)
    usage = usage.add(input_tokens=50, output_tokens=10, cost_usd=0.005)
    assert usage.input_tokens == 150
    assert usage.output_tokens == 60
    assert usage.requests == 2
    assert pytest.approx(usage.cost_usd, rel=1e-6) == 0.015


def test_ensure_within_budget_raises_on_overrun() -> None:
    usage = LlmUsage(cost_usd=0.40)
    with pytest.raises(BudgetExceededError):
        ensure_within_budget(usage=usage, additional_cost=0.20, budget_usd=0.50)


def test_ensure_within_budget_allows_under_cap() -> None:
    usage = LlmUsage(cost_usd=0.10)
    ensure_within_budget(usage=usage, additional_cost=0.20, budget_usd=0.50)


def test_budget_exceeded_error_is_sentinel_error() -> None:
    # Backwards-compat: the old `BudgetExceededError(RuntimeError)` still
    # IS-A RuntimeError so `except RuntimeError` in planner/analyzer
    # keeps catching it; the new typed lifecycle catches the SentinelError.
    err = BudgetExceededError("test", projected_usd=1.0, budget_usd=0.5)
    assert isinstance(err, RuntimeError)
    assert isinstance(err, LlmBudgetExceededError)


def test_llm_budget_pre_check_passes_under_cap() -> None:
    budget = LlmBudget(max_usd_per_run=0.50)
    budget.pre_check(caller="planner", estimated_cost_usd=0.10)
    # Adding usage moves total but doesn't change cap behavior
    budget.add(caller="planner", input_tokens=10, output_tokens=5, cost_usd=0.10)
    assert budget.usage_for("planner").cost_usd == pytest.approx(0.10)


def test_llm_budget_pre_check_breaches_caller_cap() -> None:
    budget = LlmBudget(max_usd_per_run=1.00, max_usd_planner=0.10)
    budget.add(caller="planner", input_tokens=0, output_tokens=0, cost_usd=0.08)
    with pytest.raises(LlmBudgetExceededError):
        budget.pre_check(caller="planner", estimated_cost_usd=0.05)


def test_llm_budget_pre_check_breaches_run_cap() -> None:
    budget = LlmBudget(max_usd_per_run=0.20)
    budget.add(caller="planner", input_tokens=0, output_tokens=0, cost_usd=0.15)
    with pytest.raises(LlmBudgetExceededError):
        budget.pre_check(caller="analyzer", estimated_cost_usd=0.08)


def test_llm_budget_total_sums_callers() -> None:
    budget = LlmBudget(max_usd_per_run=1.00)
    budget.add(caller="planner", input_tokens=10, output_tokens=10, cost_usd=0.05)
    budget.add(caller="analyzer", input_tokens=5, output_tokens=5, cost_usd=0.02)
    total = budget.total()
    assert total.input_tokens == 15
    assert total.output_tokens == 15
    assert pytest.approx(total.cost_usd, rel=1e-6) == 0.07
    assert total.requests == 2
