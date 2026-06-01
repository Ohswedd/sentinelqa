"""Deterministic page-budget evaluation.

The TS runtime collects N samples of LCP/CLS/INP/TTFB/DCL/load per route
and reports the median back to Python. This module evaluates the median
against the configured budgets in :class:`engine.config.schema.PerformanceBudgets`
and produces typed :class:`PageBudgetFinding` records the findings layer
translates into :class:`engine.domain.finding.Finding`.

All measurements are explicitly **synthetic**: the lab numbers
are reproducible and useful for catching regressions, but they are not
Real-User Monitoring. The finding descriptions always include the word
"synthetic" so consumers cannot mistake one for the other.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median

from engine.config.schema import PerformanceBudgets

from modules.performance.models import PageMetricSample, PageMetricsSummary

PageMetricKey = str
"""Stable identifier for a budget violation: ``lcp_ms``/``cls``/``inp_ms``/``ttfb_ms``."""


@dataclass(frozen=True)
class PageBudgetViolation:
    """One budget exceedance, ready for the findings layer."""

    metric: PageMetricKey
    observed: float
    budget: float
    samples: int
    """Number of underlying samples that fed the median."""

    @property
    def overage_pct(self) -> float:
        if self.budget == 0.0:
            return 100.0 if self.observed > 0 else 0.0
        return ((self.observed - self.budget) / self.budget) * 100.0


def summarise_samples(samples: Sequence[PageMetricSample]) -> PageMetricsSummary:
    """Return a :class:`PageMetricsSummary` (median per metric across samples).

    Samples may carry ``None`` for fields the browser could not measure
    (e.g. INP requires an interaction; not every route triggers one). We
    compute the median only over the non-null observations for each field
    and leave the median ``None`` when there is nothing to summarise.

    ``inp_supported`` is True iff at least one sample reports an INP value.
    """

    samples_tuple = tuple(samples)

    def _median_of(values: Iterable[float]) -> float | None:
        observed = [v for v in values if v is not None]
        if not observed:
            return None
        return float(median(observed))

    median_lcp = _median_of(s.lcp_ms for s in samples_tuple if s.lcp_ms is not None)
    median_cls = _median_of(s.cls for s in samples_tuple if s.cls is not None)
    median_inp = _median_of(s.inp_ms for s in samples_tuple if s.inp_ms is not None)
    median_ttfb = _median_of(s.ttfb_ms for s in samples_tuple if s.ttfb_ms is not None)
    median_dcl = _median_of(s.dcl_ms for s in samples_tuple if s.dcl_ms is not None)
    median_load = _median_of(s.load_ms for s in samples_tuple if s.load_ms is not None)
    inp_supported = any(s.inp_ms is not None for s in samples_tuple)

    return PageMetricsSummary(
        samples=samples_tuple,
        median_lcp_ms=median_lcp,
        median_cls=median_cls,
        median_inp_ms=median_inp,
        median_ttfb_ms=median_ttfb,
        median_dcl_ms=median_dcl,
        median_load_ms=median_load,
        inp_supported=inp_supported,
    )


def evaluate_page_budgets(
    summary: PageMetricsSummary,
    budgets: PerformanceBudgets,
    *,
    margin_pct: float = 0.0,
) -> tuple[PageBudgetViolation, ...]:
    """Evaluate each median against its budget; return violations.

    ``margin_pct`` adds a tolerance band — a violation is raised only when
    the observed median exceeds ``budget * (1 + margin_pct/100)``. A 0%
    margin means "strict": any overage is a violation.

    INP is only evaluated when the browser surfaced at least one sample;
    a missing INP is reported by the runner via ``inp_supported=False``
    and does NOT count as a violation (our published policy— we report
    what we measured, not what we guessed).
    """

    if margin_pct < 0.0:
        raise ValueError(f"margin_pct must be >= 0 (got {margin_pct!r}).")

    violations: list[PageBudgetViolation] = []
    factor = 1.0 + (margin_pct / 100.0)
    sample_count = len(summary.samples)

    def _check_time(metric: PageMetricKey, observed: float | None, budget: int) -> None:
        if observed is None:
            return
        ceiling = float(budget) * factor
        if observed > ceiling:
            violations.append(
                PageBudgetViolation(
                    metric=metric,
                    observed=observed,
                    budget=float(budget),
                    samples=sample_count,
                )
            )

    _check_time("lcp_ms", summary.median_lcp_ms, budgets.lcp_ms)
    _check_time("ttfb_ms", summary.median_ttfb_ms, budgets.ttfb_ms)
    if summary.inp_supported:
        _check_time("inp_ms", summary.median_inp_ms, budgets.inp_ms)
    # CLS is a small unitless score, evaluated separately so we don't
    # cast a float budget through the time-metric helper.
    if summary.median_cls is not None:
        ceiling = budgets.cls * factor
        if summary.median_cls > ceiling:
            violations.append(
                PageBudgetViolation(
                    metric="cls",
                    observed=summary.median_cls,
                    budget=budgets.cls,
                    samples=sample_count,
                )
            )
    return tuple(violations)


__all__ = [
    "PageBudgetViolation",
    "PageMetricKey",
    "evaluate_page_budgets",
    "summarise_samples",
]
