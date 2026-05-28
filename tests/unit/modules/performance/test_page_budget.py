"""Unit tests for :mod:`modules.performance.page_budget` (Phase 12.02)."""

from __future__ import annotations

import pytest
from engine.config.schema import PerformanceBudgets

from modules.performance.models import PageMetricSample
from modules.performance.page_budget import (
    evaluate_page_budgets,
    summarise_samples,
)


def _budgets(**kwargs: object) -> PerformanceBudgets:
    return PerformanceBudgets(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# summarise_samples
# ---------------------------------------------------------------------------


def test_summarise_empty_returns_all_none() -> None:
    summary = summarise_samples([])
    assert summary.samples == ()
    assert summary.median_lcp_ms is None
    assert summary.median_cls is None
    assert summary.median_inp_ms is None
    assert summary.median_ttfb_ms is None
    assert summary.inp_supported is False


def test_summarise_single_sample_round_trips() -> None:
    sample = PageMetricSample(lcp_ms=1500.0, cls=0.02, ttfb_ms=80.0, inp_ms=180.0)
    summary = summarise_samples([sample])
    assert summary.median_lcp_ms == 1500.0
    assert summary.median_cls == 0.02
    assert summary.median_ttfb_ms == 80.0
    assert summary.median_inp_ms == 180.0
    assert summary.inp_supported is True


def test_summarise_three_samples_median_is_middle() -> None:
    samples = [
        PageMetricSample(lcp_ms=1000.0, cls=0.01),
        PageMetricSample(lcp_ms=2000.0, cls=0.02),
        PageMetricSample(lcp_ms=3000.0, cls=0.03),
    ]
    summary = summarise_samples(samples)
    assert summary.median_lcp_ms == 2000.0
    assert summary.median_cls == 0.02


def test_summarise_drops_none_observations_per_metric() -> None:
    samples = [
        PageMetricSample(lcp_ms=1000.0),
        PageMetricSample(lcp_ms=None, cls=0.05),
        PageMetricSample(lcp_ms=3000.0, cls=0.01),
    ]
    summary = summarise_samples(samples)
    # LCP median over the two observed values is mean(1000, 3000) = 2000.
    assert summary.median_lcp_ms == 2000.0
    assert summary.median_cls == pytest.approx(0.03)  # median of [0.05, 0.01] = 0.03
    assert summary.inp_supported is False


# ---------------------------------------------------------------------------
# evaluate_page_budgets
# ---------------------------------------------------------------------------


def test_no_violations_when_metrics_under_budget() -> None:
    summary = summarise_samples([PageMetricSample(lcp_ms=1500.0, cls=0.05, ttfb_ms=200.0)])
    assert evaluate_page_budgets(summary, _budgets()) == ()


def test_lcp_overage_emits_violation() -> None:
    summary = summarise_samples([PageMetricSample(lcp_ms=4000.0)])
    violations = evaluate_page_budgets(summary, _budgets())
    assert len(violations) == 1
    v = violations[0]
    assert v.metric == "lcp_ms"
    assert v.observed == 4000.0
    assert v.budget == 2500.0
    assert v.overage_pct > 50.0


def test_cls_overage_emits_violation() -> None:
    summary = summarise_samples([PageMetricSample(cls=0.5)])
    violations = evaluate_page_budgets(summary, _budgets())
    assert len(violations) == 1
    assert violations[0].metric == "cls"


def test_ttfb_overage_emits_violation() -> None:
    summary = summarise_samples([PageMetricSample(ttfb_ms=1000.0)])
    violations = evaluate_page_budgets(summary, _budgets())
    assert any(v.metric == "ttfb_ms" for v in violations)


def test_inp_only_evaluated_when_supported() -> None:
    summary_unsupported = summarise_samples([PageMetricSample(lcp_ms=1000.0)])
    assert all(v.metric != "inp_ms" for v in evaluate_page_budgets(summary_unsupported, _budgets()))

    summary_supported = summarise_samples([PageMetricSample(inp_ms=800.0)])
    inp_violations = [
        v for v in evaluate_page_budgets(summary_supported, _budgets()) if v.metric == "inp_ms"
    ]
    assert len(inp_violations) == 1


def test_margin_pct_relaxes_the_check() -> None:
    # LCP budget 2500ms; observed 2700ms (8% overage). 10% margin → no violation.
    summary = summarise_samples([PageMetricSample(lcp_ms=2700.0)])
    assert evaluate_page_budgets(summary, _budgets(), margin_pct=10.0) == ()
    # 0% margin → violation.
    assert len(evaluate_page_budgets(summary, _budgets(), margin_pct=0.0)) == 1


def test_negative_margin_raises() -> None:
    summary = summarise_samples([PageMetricSample(lcp_ms=1000.0)])
    with pytest.raises(ValueError):
        evaluate_page_budgets(summary, _budgets(), margin_pct=-1.0)


def test_zero_budget_overage_pct_reports_100_when_observed_nonzero() -> None:
    summary = summarise_samples([PageMetricSample(lcp_ms=500.0)])
    violations = evaluate_page_budgets(summary, _budgets(lcp_ms=0))
    assert len(violations) == 1
    assert violations[0].overage_pct == 100.0


def test_overage_severity_buckets() -> None:
    """Severity thresholds: ≤50% → medium; >50% → high (via overage_pct)."""

    # 60% overage above budget 2500 → 4000.
    summary = summarise_samples([PageMetricSample(lcp_ms=4000.0)])
    v = evaluate_page_budgets(summary, _budgets())[0]
    assert v.overage_pct == pytest.approx(60.0)

    # 20% overage above budget 2500 → 3000.
    summary = summarise_samples([PageMetricSample(lcp_ms=3000.0)])
    v = evaluate_page_budgets(summary, _budgets())[0]
    assert v.overage_pct == pytest.approx(20.0)
