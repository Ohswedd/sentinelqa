"""Repeated-navigation stability heuristic.

The TS runtime visits each route N times (default 5) and samples the JS
heap size + DOM-node count after each visit. This module computes the
growth from the first to the last sample and emits a low-confidence
``potential-memory-leak`` finding when growth exceeds the configured
threshold.

CLAUDE §27 reminder: this is a heuristic. A small growth is normal
(caches warming, background telemetry). The finding text says
"potential" and confidence is intentionally below 1.0 so the Phase-14
quality gate does not over-fail on noise.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from engine.config.schema import PerformanceBudgets

from modules.performance.models import NavStabilitySample, NavStabilitySummary


def _growth_pct(first: float, last: float) -> float:
    if first == 0.0:
        return 100.0 if last > 0 else 0.0
    return ((last - first) / first) * 100.0


def summarise_nav_samples(samples: Sequence[NavStabilitySample]) -> NavStabilitySummary:
    """Compute the dom/memory growth pct between the first and last sample."""

    samples_tuple = tuple(samples)
    dom_growth: float | None = None
    memory_growth: float | None = None
    memory_supported = False
    if len(samples_tuple) >= 2:
        first, last = samples_tuple[0], samples_tuple[-1]
        if first.dom_node_count is not None and last.dom_node_count is not None:
            dom_growth = _growth_pct(float(first.dom_node_count), float(last.dom_node_count))
        if first.js_heap_bytes is not None and last.js_heap_bytes is not None:
            memory_growth = _growth_pct(first.js_heap_bytes, last.js_heap_bytes)
            memory_supported = True
    return NavStabilitySummary(
        samples=samples_tuple,
        dom_growth_pct=dom_growth,
        memory_growth_pct=memory_growth,
        memory_supported=memory_supported,
    )


@dataclass(frozen=True)
class NavStabilityViolation:
    """One growth metric exceeded its configured tolerance."""

    metric: str
    """Either ``dom`` or ``memory``."""
    observed_pct: float
    threshold_pct: float
    samples: int


def evaluate_nav_stability(
    summary: NavStabilitySummary,
    budgets: PerformanceBudgets,
) -> tuple[NavStabilityViolation, ...]:
    """Compare DOM + memory growth pct against budgets; emit violations.

    A growth value of ``None`` means the runner could not measure that
    metric (e.g. ``performance.memory`` is not supported in Firefox/WebKit).
    Missing measurements are not violations.
    """

    violations: list[NavStabilityViolation] = []
    sample_count = len(summary.samples)
    if summary.dom_growth_pct is not None and summary.dom_growth_pct > budgets.dom_growth_pct:
        violations.append(
            NavStabilityViolation(
                metric="dom",
                observed_pct=summary.dom_growth_pct,
                threshold_pct=budgets.dom_growth_pct,
                samples=sample_count,
            )
        )
    if (
        summary.memory_supported
        and summary.memory_growth_pct is not None
        and summary.memory_growth_pct > budgets.memory_growth_pct
    ):
        violations.append(
            NavStabilityViolation(
                metric="memory",
                observed_pct=summary.memory_growth_pct,
                threshold_pct=budgets.memory_growth_pct,
                samples=sample_count,
            )
        )
    return tuple(violations)


__all__ = [
    "NavStabilityViolation",
    "evaluate_nav_stability",
    "summarise_nav_samples",
]
