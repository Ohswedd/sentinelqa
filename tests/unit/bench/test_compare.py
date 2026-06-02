# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the SLO baseline comparator."""

from __future__ import annotations

from engine.bench import (
    DEFAULT_REGRESSION_THRESHOLD,
    BenchMetric,
    BenchReport,
    compare_to_baseline,
)


def _report(import_s: float, full_s: float) -> BenchReport:
    return BenchReport(
        metrics=(
            BenchMetric(name="import_time_s", value_seconds=import_s, samples=3),
            BenchMetric(name="full_audit_s", value_seconds=full_s, samples=2),
        ),
    )


def test_no_regression_inside_threshold() -> None:
    baseline = _report(import_s=0.40, full_s=1.50)
    measured = _report(import_s=0.43, full_s=1.55)  # +7.5% / +3.3%
    comparison = compare_to_baseline(measured, baseline)
    assert not comparison.has_regressions
    assert comparison.regressions == ()


def test_regression_above_threshold() -> None:
    baseline = _report(import_s=0.40, full_s=1.50)
    measured = _report(import_s=0.50, full_s=1.55)  # +25% / +3.3%
    comparison = compare_to_baseline(measured, baseline)
    assert comparison.has_regressions
    names = [r.name for r in comparison.regressions]
    assert "import_time_s" in names
    assert "full_audit_s" not in names


def test_per_metric_threshold_override() -> None:
    baseline = _report(import_s=0.40, full_s=1.50)
    measured = _report(import_s=0.40, full_s=1.80)  # +20% full audit
    comparison = compare_to_baseline(
        measured,
        baseline,
        per_metric_threshold={"full_audit_s": 0.25},
    )
    assert not comparison.has_regressions


def test_default_threshold_is_ten_percent() -> None:
    assert DEFAULT_REGRESSION_THRESHOLD == 0.10


def test_metric_missing_from_report_is_flagged() -> None:
    baseline = _report(import_s=0.40, full_s=1.50)
    measured = BenchReport(
        metrics=(BenchMetric(name="import_time_s", value_seconds=0.40, samples=3),),
    )
    comparison = compare_to_baseline(measured, baseline)
    assert "full_audit_s" in comparison.missing_in_report


def test_metric_new_to_report_is_flagged() -> None:
    baseline = _report(import_s=0.40, full_s=1.50)
    measured = BenchReport(
        metrics=(
            BenchMetric(name="import_time_s", value_seconds=0.40, samples=3),
            BenchMetric(name="full_audit_s", value_seconds=1.50, samples=2),
            BenchMetric(name="new_metric_s", value_seconds=0.10, samples=1),
        ),
    )
    comparison = compare_to_baseline(measured, baseline)
    assert "new_metric_s" in comparison.missing_in_baseline


def test_render_text_for_pass() -> None:
    baseline = _report(import_s=0.40, full_s=1.50)
    measured = _report(import_s=0.40, full_s=1.50)
    text = compare_to_baseline(measured, baseline).render_text()
    assert "OK" in text


def test_render_text_for_regression() -> None:
    baseline = _report(import_s=0.40, full_s=1.50)
    measured = _report(import_s=0.60, full_s=1.50)  # +50%
    text = compare_to_baseline(measured, baseline).render_text()
    assert "REGRESSION" in text
    assert "import_time_s" in text


def test_zero_baseline_value_is_skipped() -> None:
    baseline = BenchReport(
        metrics=(BenchMetric(name="foo_s", value_seconds=0.0, samples=1),),
    )
    measured = BenchReport(
        metrics=(BenchMetric(name="foo_s", value_seconds=10.0, samples=1),),
    )
    comparison = compare_to_baseline(measured, baseline)
    assert not comparison.has_regressions
