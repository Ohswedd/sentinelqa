"""Unit tests for :mod:`modules.performance.api_latency`."""

from __future__ import annotations

import pytest
from engine.config.schema import PerformanceBudgets

from modules.performance.api_latency import (
    evaluate_api_latency,
    percentile,
    summarise_api_samples,
    template_endpoint,
)
from modules.performance.models import ApiSample

# ---------------------------------------------------------------------------
# template_endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/api/users/42", "/api/users/[id]"),
        ("/api/users/42/posts/9", "/api/users/[id]/posts/[id]"),
        (
            "/api/items/01234567-89ab-cdef-0123-456789abcdef",
            "/api/items/[uuid]",
        ),
        ("/api/items/deadbeef1234", "/api/items/[hex]"),
        ("/api/items/abc123def456", "/api/items/[hex]"),
        ("/api/static", "/api/static"),
        ("/api/users/42?expand=posts", "/api/users/[id]"),
        ("/api/users/42#anchor", "/api/users/[id]"),
        ("", ""),
    ],
)
def test_template_endpoint(raw: str, expected: str) -> None:
    assert template_endpoint(raw) == expected


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------


def test_percentile_empty_returns_zero() -> None:
    assert percentile([], 95.0) == 0.0


def test_percentile_single_value() -> None:
    assert percentile([42.0], 95.0) == 42.0


def test_percentile_quartile_interpolation() -> None:
    # NIST type-7: P50 of [1,2,3,4] = (2+3)/2 = 2.5
    assert percentile([1.0, 2.0, 3.0, 4.0], 50.0) == pytest.approx(2.5)


def test_percentile_p95_of_twenty_samples() -> None:
    values = [float(i + 1) for i in range(20)]  # 1..20
    # P95 of 20 evenly spaced points = ~19.05
    assert percentile(values, 95.0) == pytest.approx(19.05)


def test_percentile_invalid_pct_raises() -> None:
    with pytest.raises(ValueError):
        percentile([1.0, 2.0], 101.0)


# ---------------------------------------------------------------------------
# summarise_api_samples
# ---------------------------------------------------------------------------


def test_summarise_groups_by_method_and_endpoint() -> None:
    samples = [
        ApiSample(endpoint="/api/users/42", method="GET", duration_ms=50.0, status=200),
        ApiSample(endpoint="/api/users/99", method="GET", duration_ms=70.0, status=200),
        ApiSample(endpoint="/api/users", method="POST", duration_ms=200.0, status=201),
        ApiSample(endpoint="/api/users/7", method="GET", duration_ms=60.0, status=200),
    ]
    summaries = summarise_api_samples(samples)
    assert len(summaries) == 2
    by_key = {(s.method, s.endpoint): s for s in summaries}
    get_users = by_key[("GET", "/api/users/[id]")]
    assert get_users.count == 3
    assert get_users.max_ms == 70.0
    post_users = by_key[("POST", "/api/users")]
    assert post_users.count == 1


def test_summarise_is_deterministic_sorted() -> None:
    samples = [
        ApiSample(endpoint="/b", method="GET", duration_ms=10.0, status=200),
        ApiSample(endpoint="/a", method="GET", duration_ms=20.0, status=200),
        ApiSample(endpoint="/a", method="POST", duration_ms=30.0, status=200),
    ]
    keys = [(s.method, s.endpoint) for s in summarise_api_samples(samples)]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# evaluate_api_latency
# ---------------------------------------------------------------------------


def _samples_at(duration_ms: float, count: int, endpoint: str = "/api/x") -> list[ApiSample]:
    return [
        ApiSample(endpoint=endpoint, method="GET", duration_ms=duration_ms, status=200)
        for _ in range(count)
    ]


def test_no_violation_when_p95_under_budget() -> None:
    summaries = summarise_api_samples(_samples_at(100.0, 10))
    assert evaluate_api_latency(summaries, PerformanceBudgets()) == ()


def test_violation_when_p95_over_budget() -> None:
    summaries = summarise_api_samples(_samples_at(900.0, 10))
    violations = evaluate_api_latency(summaries, PerformanceBudgets())
    assert len(violations) == 1
    v = violations[0]
    assert v.endpoint == "/api/x"
    assert v.observed_p95_ms == pytest.approx(900.0)
    assert v.overage_pct == pytest.approx(80.0)


def test_violation_severity_threshold_at_overage_100() -> None:
    summaries = summarise_api_samples(_samples_at(1500.0, 10))
    v = evaluate_api_latency(summaries, PerformanceBudgets())[0]
    assert v.overage_pct == pytest.approx(200.0)


def test_endpoints_below_min_samples_are_skipped() -> None:
    summaries = summarise_api_samples(_samples_at(2000.0, 3))
    # min_samples default 5 — 3 observations is not enough for a P95.
    assert evaluate_api_latency(summaries, PerformanceBudgets()) == ()


def test_margin_pct_relaxes_threshold() -> None:
    summaries = summarise_api_samples(_samples_at(520.0, 10))  # 4% over 500.
    assert evaluate_api_latency(summaries, PerformanceBudgets(), margin_pct=10.0) == ()
    assert len(evaluate_api_latency(summaries, PerformanceBudgets(), margin_pct=0.0)) == 1


def test_negative_margin_raises() -> None:
    summaries = summarise_api_samples(_samples_at(100.0, 10))
    with pytest.raises(ValueError):
        evaluate_api_latency(summaries, PerformanceBudgets(), margin_pct=-1.0)


def test_zero_min_samples_raises() -> None:
    summaries = summarise_api_samples(_samples_at(100.0, 10))
    with pytest.raises(ValueError):
        evaluate_api_latency(summaries, PerformanceBudgets(), min_samples=0)


def test_zero_budget_overage_reports_100_when_observed_nonzero() -> None:
    summaries = summarise_api_samples(_samples_at(50.0, 10))
    v = evaluate_api_latency(summaries, PerformanceBudgets(api_p95_ms=0))[0]
    assert v.overage_pct == 100.0
