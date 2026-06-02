# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""SLO benchmark suite (v1.8.0, phase 38).

Reproducible wall-clock measurements for the four metrics that decide
whether release engineering is on track:

* **import time** — how long ``python -c "import sentinel_cli"`` takes.
* **CLI cold-start** — how long ``sentinel --version`` takes from
  process spawn to exit.
* **time-to-first-finding** — how long from ``sentinel discover``
  spawn until the first emitted route lands in ``discovery.json``.
* **full-audit wall-clock** — total time for a hermetic
  ``sentinel discover`` against the canned audit-of-self fixture.

The metrics are intentionally bounded and reproducible — they run
against the same stdlib HTTP fixture the audit-of-self CI gate uses
(see :mod:`scripts.audit-of-self`). No browser. No network.

Public entry points:

* :func:`run_bench` — measure all four metrics and return a
  :class:`BenchReport`.
* :func:`compare_to_baseline` — apply a per-metric ``threshold_ratio``
  and emit a :class:`SloComparison` summarising regressions.
* :func:`write_report` / :func:`load_report` — round-trip the report
  via JSON for CI artefacts.
"""

from __future__ import annotations

from engine.bench.compare import (
    DEFAULT_REGRESSION_THRESHOLD,
    SloComparison,
    SloRegression,
    compare_to_baseline,
)
from engine.bench.report import (
    BenchMetric,
    BenchReport,
    load_report,
    write_report,
)
from engine.bench.runner import run_bench

__all__ = [
    "DEFAULT_REGRESSION_THRESHOLD",
    "BenchMetric",
    "BenchReport",
    "SloComparison",
    "SloRegression",
    "compare_to_baseline",
    "load_report",
    "run_bench",
    "write_report",
]
