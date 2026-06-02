# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Baseline comparison + SLO gating."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from engine.bench.report import BenchReport

# Fail CI if any metric has slipped more than 10 % from its baseline.
# A per-metric threshold can override this in the baseline file (the
# heaviest metrics — full audit — are noisier and tend to need 15 %).
DEFAULT_REGRESSION_THRESHOLD: Final[float] = 0.10


@dataclass(frozen=True, slots=True)
class SloRegression:
    """One regressed metric."""

    name: str
    baseline_seconds: float
    measured_seconds: float
    ratio: float  # measured / baseline; e.g. 1.18 means +18 %.
    threshold_ratio: float


@dataclass(frozen=True, slots=True)
class SloComparison:
    """Outcome of comparing a measured :class:`BenchReport` to baseline."""

    has_regressions: bool
    regressions: tuple[SloRegression, ...] = field(default_factory=tuple)
    missing_in_baseline: tuple[str, ...] = field(default_factory=tuple)
    missing_in_report: tuple[str, ...] = field(default_factory=tuple)

    def render_text(self) -> str:
        """Human-readable diff used by ``sentinel bench --compare-to``."""

        lines: list[str] = []
        if not self.has_regressions and not self.missing_in_report:
            lines.append("OK — all SLOs within threshold.")
        for regression in self.regressions:
            slowdown_pct = (regression.ratio - 1.0) * 100.0
            lines.append(
                f"REGRESSION  {regression.name}: "
                f"{regression.measured_seconds:.3f}s vs baseline "
                f"{regression.baseline_seconds:.3f}s "
                f"(+{slowdown_pct:.1f}%, threshold "
                f"+{regression.threshold_ratio * 100:.0f}%)"
            )
        for missing in self.missing_in_report:
            lines.append(f"MISSING     {missing} not measured this run.")
        for extra in self.missing_in_baseline:
            lines.append(f"NEW         {extra} has no baseline entry.")
        return "\n".join(lines)


def compare_to_baseline(
    measured: BenchReport,
    baseline: BenchReport,
    *,
    default_threshold: float = DEFAULT_REGRESSION_THRESHOLD,
    per_metric_threshold: dict[str, float] | None = None,
) -> SloComparison:
    """Compare ``measured`` against ``baseline`` and return regressions.

    A metric counts as a regression when
    ``measured / baseline > 1 + threshold_ratio``.

    ``per_metric_threshold`` lets callers loosen one metric without
    changing the global default (used for noisier metrics like the full
    audit run).
    """

    overrides = per_metric_threshold or {}
    baseline_by_name = {m.name: m for m in baseline.metrics}
    measured_by_name = {m.name: m for m in measured.metrics}

    regressions: list[SloRegression] = []
    for name, measured_metric in measured_by_name.items():
        if name not in baseline_by_name:
            continue
        baseline_metric = baseline_by_name[name]
        threshold = overrides.get(name, default_threshold)
        if baseline_metric.value_seconds <= 0.0:
            continue
        ratio = measured_metric.value_seconds / baseline_metric.value_seconds
        if ratio > 1.0 + threshold:
            regressions.append(
                SloRegression(
                    name=name,
                    baseline_seconds=baseline_metric.value_seconds,
                    measured_seconds=measured_metric.value_seconds,
                    ratio=ratio,
                    threshold_ratio=threshold,
                )
            )

    missing_in_report = tuple(sorted(set(baseline_by_name) - set(measured_by_name)))
    missing_in_baseline = tuple(sorted(set(measured_by_name) - set(baseline_by_name)))

    return SloComparison(
        has_regressions=bool(regressions),
        regressions=tuple(regressions),
        missing_in_baseline=missing_in_baseline,
        missing_in_report=missing_in_report,
    )


__all__ = [
    "DEFAULT_REGRESSION_THRESHOLD",
    "SloComparison",
    "SloRegression",
    "compare_to_baseline",
]
