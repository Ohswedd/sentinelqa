# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Read-only helpers for inspecting completed run directories.

The artifact tree on disk is the source of truth for every
post-hoc query: ``sentinel ask`` answers natural-language questions
about it, ``sentinel.compare_runs`` diffs two of them,
``sentinel.coverage_gaps`` cross-references it with discovery.
"""

from __future__ import annotations

from engine.runs.compare import RunComparison, compare_runs
from engine.runs.coverage import CoverageGap, CoverageReport, find_coverage_gaps
from engine.runs.summary import RunSummary, load_run_summary

__all__ = [
    "CoverageGap",
    "CoverageReport",
    "RunComparison",
    "RunSummary",
    "compare_runs",
    "find_coverage_gaps",
    "load_run_summary",
]
