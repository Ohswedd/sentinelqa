"""Unit tests for :mod:`modules.performance.bundle_cpu` (Phase 12.04)."""

from __future__ import annotations

import pytest
from engine.config.schema import PerformanceBudgets

from modules.performance.bundle_cpu import (
    evaluate_bundle_size,
    evaluate_long_tasks,
)
from modules.performance.models import BundleSummary, LongTaskSummary

# ---------------------------------------------------------------------------
# Bundle size
# ---------------------------------------------------------------------------


def test_no_bundle_violation_when_under_budget() -> None:
    summary = BundleSummary(transfer_total_kb=400.0, decoded_total_kb=900.0, file_count=4)
    assert evaluate_bundle_size(summary, PerformanceBudgets()) is None


def test_bundle_violation_when_over_budget() -> None:
    summary = BundleSummary(transfer_total_kb=800.0, decoded_total_kb=1600.0, file_count=10)
    violation = evaluate_bundle_size(summary, PerformanceBudgets())
    assert violation is not None
    assert violation.observed_kb == 800.0
    assert violation.budget_kb == 500
    assert violation.overage_pct == pytest.approx(60.0)


def test_bundle_margin_relaxes_threshold() -> None:
    summary = BundleSummary(transfer_total_kb=520.0, decoded_total_kb=900.0, file_count=4)
    # 10% margin → budget 550 KB; 520 KB is fine.
    assert evaluate_bundle_size(summary, PerformanceBudgets(), margin_pct=10.0) is None
    # 0% margin → 520 KB > 500 KB budget.
    assert evaluate_bundle_size(summary, PerformanceBudgets(), margin_pct=0.0) is not None


def test_bundle_negative_margin_raises() -> None:
    summary = BundleSummary(transfer_total_kb=100.0, decoded_total_kb=100.0, file_count=1)
    with pytest.raises(ValueError):
        evaluate_bundle_size(summary, PerformanceBudgets(), margin_pct=-1.0)


def test_bundle_zero_budget_reports_overage_100() -> None:
    summary = BundleSummary(transfer_total_kb=200.0, decoded_total_kb=200.0, file_count=1)
    violation = evaluate_bundle_size(summary, PerformanceBudgets(js_total_kb=0))
    assert violation is not None
    assert violation.overage_pct == 100.0


# ---------------------------------------------------------------------------
# Long tasks
# ---------------------------------------------------------------------------


def test_no_long_task_violation_when_under_budget() -> None:
    summary = LongTaskSummary(count=2, total_blocking_ms=100.0, longest_ms=60.0)
    assert evaluate_long_tasks(summary, PerformanceBudgets()) is None


def test_long_task_violation_when_over_budget() -> None:
    summary = LongTaskSummary(count=5, total_blocking_ms=500.0, longest_ms=120.0)
    violation = evaluate_long_tasks(summary, PerformanceBudgets())
    assert violation is not None
    assert violation.total_blocking_ms == 500.0
    assert violation.budget_ms == 200
    assert violation.overage_pct == pytest.approx(150.0)


def test_long_task_margin_relaxes_threshold() -> None:
    summary = LongTaskSummary(count=2, total_blocking_ms=210.0, longest_ms=80.0)
    assert evaluate_long_tasks(summary, PerformanceBudgets(), margin_pct=10.0) is None
    assert evaluate_long_tasks(summary, PerformanceBudgets(), margin_pct=0.0) is not None


def test_long_task_negative_margin_raises() -> None:
    summary = LongTaskSummary(count=1, total_blocking_ms=50.0, longest_ms=50.0)
    with pytest.raises(ValueError):
        evaluate_long_tasks(summary, PerformanceBudgets(), margin_pct=-1.0)


def test_long_task_zero_budget_reports_overage_100() -> None:
    summary = LongTaskSummary(count=1, total_blocking_ms=50.0, longest_ms=50.0)
    violation = evaluate_long_tasks(summary, PerformanceBudgets(long_task_total_ms=0))
    assert violation is not None
    assert violation.overage_pct == 100.0
