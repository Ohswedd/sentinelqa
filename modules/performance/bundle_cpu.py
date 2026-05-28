"""Bundle size + CPU blocking evaluators (Phase 12.04, PRD §10.5, CLAUDE §27).

The TS runtime sums every JavaScript response's transfer + decoded size
during the synthetic page loads and observes long tasks via
``PerformanceObserver({ entryTypes: ['longtask'] })``. This module
evaluates those aggregates against the configured budgets.

CLAUDE §27 reminder: long-task counts are lab synthetic measurements.
A blocked main thread in a headless browser is a real signal, but it is
not the same as a blocked main thread on a constrained user device. The
finding text says so explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.config.schema import PerformanceBudgets

from modules.performance.models import BundleSummary, LongTaskSummary


@dataclass(frozen=True)
class BundleSizeViolation:
    """Total transferred JS exceeded the bundle budget."""

    observed_kb: float
    budget_kb: int
    file_count: int

    @property
    def overage_pct(self) -> float:
        if self.budget_kb == 0:
            return 100.0 if self.observed_kb > 0 else 0.0
        return ((self.observed_kb - float(self.budget_kb)) / float(self.budget_kb)) * 100.0


@dataclass(frozen=True)
class LongTaskViolation:
    """Cumulative blocking time exceeded the long-task budget."""

    total_blocking_ms: float
    longest_ms: float
    count: int
    budget_ms: int

    @property
    def overage_pct(self) -> float:
        if self.budget_ms == 0:
            return 100.0 if self.total_blocking_ms > 0 else 0.0
        return ((self.total_blocking_ms - float(self.budget_ms)) / float(self.budget_ms)) * 100.0


def evaluate_bundle_size(
    summary: BundleSummary,
    budgets: PerformanceBudgets,
    *,
    margin_pct: float = 0.0,
) -> BundleSizeViolation | None:
    """Compare the transferred-bytes total against ``budgets.js_total_kb``.

    The transferred total is the wire-bytes figure (after compression);
    we prefer it over the decoded total because it is what users
    actually download. The decoded total is preserved in the summary
    for the report layer to surface alongside.
    """

    if margin_pct < 0.0:
        raise ValueError(f"margin_pct must be >= 0 (got {margin_pct!r}).")
    ceiling = float(budgets.js_total_kb) * (1.0 + margin_pct / 100.0)
    if summary.transfer_total_kb <= ceiling:
        return None
    return BundleSizeViolation(
        observed_kb=summary.transfer_total_kb,
        budget_kb=budgets.js_total_kb,
        file_count=summary.file_count,
    )


def evaluate_long_tasks(
    summary: LongTaskSummary,
    budgets: PerformanceBudgets,
    *,
    margin_pct: float = 0.0,
) -> LongTaskViolation | None:
    """Compare cumulative blocking time against ``budgets.long_task_total_ms``."""

    if margin_pct < 0.0:
        raise ValueError(f"margin_pct must be >= 0 (got {margin_pct!r}).")
    ceiling = float(budgets.long_task_total_ms) * (1.0 + margin_pct / 100.0)
    if summary.total_blocking_ms <= ceiling:
        return None
    return LongTaskViolation(
        total_blocking_ms=summary.total_blocking_ms,
        longest_ms=summary.longest_ms,
        count=summary.count,
        budget_ms=budgets.long_task_total_ms,
    )


__all__ = [
    "BundleSizeViolation",
    "LongTaskViolation",
    "evaluate_bundle_size",
    "evaluate_long_tasks",
]
