"""API latency budgets (Phase 12.03, the documentation, CLAUDE §27).

The TS runtime observes every XHR/fetch response during the synthetic
page loads and reports the raw samples + a per-endpoint summary. This
module evaluates the templated endpoint's P95 against the configured
budget and returns typed violations.

Endpoint paths are templated identically to Phase 05's
:class:`engine.discovery.api_detector` (`/api/users/[id]`,
`/api/users/[uuid]`, `/api/users/[hex]`) so that grouped samples don't
fragment across each user's id.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

from engine.config.schema import PerformanceBudgets

from modules.performance.models import ApiEndpointSummary, ApiSample

# Pre-compiled templating rules (kept in sync with discovery's api_detector).
_TEMPLATERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), "/[uuid]"),
    (re.compile(r"/[0-9a-f]{12,}", re.I), "/[hex]"),
    (re.compile(r"/\d+"), "/[id]"),
)


def template_endpoint(path: str) -> str:
    """Normalise dynamic path segments (`/users/42` → `/users/[id]`).

    The query string is stripped so endpoints group by route, not by
    parameter values.
    """

    if not path:
        return path
    cleaned = path.split("?", 1)[0].split("#", 1)[0]
    for pattern, replacement in _TEMPLATERS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def percentile(values: Iterable[float], pct: float) -> float:
    """Linear-interpolation percentile (NIST type-7).

    Returns 0.0 when ``values`` is empty. ``pct`` is 0-100.
    """

    if not 0.0 <= pct <= 100.0:
        raise ValueError(f"pct must be in [0,100] (got {pct!r}).")
    sorted_values = sorted(values)
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    frac = rank - lower
    return float(sorted_values[lower]) * (1.0 - frac) + float(sorted_values[upper]) * frac


def summarise_api_samples(
    samples: Iterable[ApiSample],
) -> tuple[ApiEndpointSummary, ...]:
    """Group raw samples by (method, templated endpoint); compute P50/P95.

    The grouping is stable: results are returned sorted by (method,
    endpoint) so the JSON wire-format is deterministic across runs.
    """

    buckets: dict[tuple[str, str], list[float]] = {}
    for sample in samples:
        key = (sample.method.upper(), template_endpoint(sample.endpoint))
        buckets.setdefault(key, []).append(sample.duration_ms)

    summaries: list[ApiEndpointSummary] = []
    for (method, endpoint), durations in sorted(buckets.items()):
        summaries.append(
            ApiEndpointSummary(
                endpoint=endpoint,
                method=method,
                count=len(durations),
                p50_ms=percentile(durations, 50.0),
                p95_ms=percentile(durations, 95.0),
                max_ms=max(durations),
            )
        )
    return tuple(summaries)


@dataclass(frozen=True)
class ApiLatencyViolation:
    """One endpoint's P95 exceeding the configured budget."""

    endpoint: str
    method: str
    observed_p95_ms: float
    budget_p95_ms: int
    samples: int

    @property
    def overage_pct(self) -> float:
        if self.budget_p95_ms == 0:
            return 100.0 if self.observed_p95_ms > 0 else 0.0
        return (
            (self.observed_p95_ms - float(self.budget_p95_ms)) / float(self.budget_p95_ms)
        ) * 100.0


def evaluate_api_latency(
    summaries: Iterable[ApiEndpointSummary],
    budgets: PerformanceBudgets,
    *,
    min_samples: int = 5,
    margin_pct: float = 0.0,
) -> tuple[ApiLatencyViolation, ...]:
    """Evaluate each endpoint summary against the configured P95 budget.

    Endpoints with fewer than ``min_samples`` observations are skipped —
    P95 from 2 samples is not actually a percentile. ``margin_pct`` adds a
    tolerance band consistent with :func:`evaluate_page_budgets`.
    """

    if margin_pct < 0.0:
        raise ValueError(f"margin_pct must be >= 0 (got {margin_pct!r}).")
    if min_samples < 1:
        raise ValueError(f"min_samples must be >= 1 (got {min_samples!r}).")

    ceiling = float(budgets.api_p95_ms) * (1.0 + margin_pct / 100.0)
    violations: list[ApiLatencyViolation] = []
    for summary in summaries:
        if summary.count < min_samples:
            continue
        if summary.p95_ms > ceiling:
            violations.append(
                ApiLatencyViolation(
                    endpoint=summary.endpoint,
                    method=summary.method,
                    observed_p95_ms=summary.p95_ms,
                    budget_p95_ms=budgets.api_p95_ms,
                    samples=summary.count,
                )
            )
    return tuple(violations)


__all__ = [
    "ApiLatencyViolation",
    "evaluate_api_latency",
    "percentile",
    "summarise_api_samples",
    "template_endpoint",
]
