"""Unit tests for :mod:`modules.performance.nav_stability` (Phase 12.05)."""

from __future__ import annotations

from engine.config.schema import PerformanceBudgets

from modules.performance.models import NavStabilitySample
from modules.performance.nav_stability import (
    evaluate_nav_stability,
    summarise_nav_samples,
)

# ---------------------------------------------------------------------------
# summarise_nav_samples
# ---------------------------------------------------------------------------


def test_summarise_empty_returns_none_growth() -> None:
    summary = summarise_nav_samples([])
    assert summary.dom_growth_pct is None
    assert summary.memory_growth_pct is None
    assert summary.memory_supported is False


def test_summarise_single_sample_returns_none_growth() -> None:
    summary = summarise_nav_samples([NavStabilitySample(js_heap_bytes=1.0, dom_node_count=10)])
    assert summary.dom_growth_pct is None
    assert summary.memory_growth_pct is None


def test_summarise_stable_samples_zero_growth() -> None:
    samples = [
        NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
        NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
        NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
    ]
    summary = summarise_nav_samples(samples)
    assert summary.dom_growth_pct == 0.0
    assert summary.memory_growth_pct == 0.0
    assert summary.memory_supported is True


def test_summarise_growing_samples_positive_pct() -> None:
    samples = [
        NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
        NavStabilitySample(js_heap_bytes=1200.0, dom_node_count=110),
        NavStabilitySample(js_heap_bytes=1500.0, dom_node_count=130),
    ]
    summary = summarise_nav_samples(samples)
    assert summary.dom_growth_pct == 30.0
    assert summary.memory_growth_pct == 50.0


def test_summarise_memory_unsupported_when_missing() -> None:
    samples = [
        NavStabilitySample(js_heap_bytes=None, dom_node_count=100),
        NavStabilitySample(js_heap_bytes=None, dom_node_count=110),
    ]
    summary = summarise_nav_samples(samples)
    assert summary.memory_supported is False
    assert summary.memory_growth_pct is None
    assert summary.dom_growth_pct == 10.0


def test_summarise_shrink_is_negative_pct() -> None:
    samples = [
        NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
        NavStabilitySample(js_heap_bytes=900.0, dom_node_count=90),
    ]
    summary = summarise_nav_samples(samples)
    assert summary.dom_growth_pct == -10.0
    assert summary.memory_growth_pct == -10.0


# ---------------------------------------------------------------------------
# evaluate_nav_stability
# ---------------------------------------------------------------------------


def test_no_violation_when_stable() -> None:
    summary = summarise_nav_samples(
        [
            NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
            NavStabilitySample(js_heap_bytes=1010.0, dom_node_count=101),
        ]
    )
    assert evaluate_nav_stability(summary, PerformanceBudgets()) == ()


def test_dom_growth_over_threshold_emits_violation() -> None:
    summary = summarise_nav_samples(
        [
            NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
            NavStabilitySample(js_heap_bytes=1010.0, dom_node_count=150),
        ]
    )
    violations = evaluate_nav_stability(summary, PerformanceBudgets())
    metrics = {v.metric for v in violations}
    assert "dom" in metrics


def test_memory_growth_over_threshold_emits_violation() -> None:
    summary = summarise_nav_samples(
        [
            NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
            NavStabilitySample(js_heap_bytes=1500.0, dom_node_count=101),
        ]
    )
    violations = evaluate_nav_stability(summary, PerformanceBudgets())
    metrics = {v.metric for v in violations}
    assert "memory" in metrics


def test_memory_unsupported_skips_memory_violation_even_when_dom_grows() -> None:
    samples = [
        NavStabilitySample(js_heap_bytes=None, dom_node_count=100),
        NavStabilitySample(js_heap_bytes=None, dom_node_count=200),
    ]
    summary = summarise_nav_samples(samples)
    violations = evaluate_nav_stability(summary, PerformanceBudgets())
    metrics = {v.metric for v in violations}
    assert metrics == {"dom"}


def test_missing_growth_skips_check() -> None:
    summary = summarise_nav_samples([NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100)])
    assert evaluate_nav_stability(summary, PerformanceBudgets()) == ()
