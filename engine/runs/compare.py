# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Diff two runs and produce a :class:`RunComparison`.

A "diff" is a set-difference over a fingerprint that identifies the
*same logical issue* across runs. Two findings are considered the
same when their ``(module, category, code, title)`` quadruple
matches; this is stable across run IDs and across timestamps but
sensitive to "the same check now fires on a new endpoint" (which we
want to surface as a separate fingerprint).

Output:

* ``new``: findings present in ``after`` but not in ``before``.
* ``resolved``: findings present in ``before`` but not in ``after``.
* ``persistent``: findings present in both.
* ``severity_regressions``: findings that exist in both but escalated.
* ``score_delta``: ``after.quality_score - before.quality_score``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from engine.runs.summary import FindingRef, RunSummary, severity_breakdown

_SEVERITY_ORDER: Final[dict[str, int]] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _fingerprint(finding: FindingRef) -> tuple[str, str, str, str]:
    return (finding.module, finding.category, finding.code, finding.title)


@dataclass(frozen=True, slots=True)
class SeverityChange:
    """A finding that exists in both runs but escalated / de-escalated."""

    before: FindingRef
    after: FindingRef
    direction: str  # "regressed" | "improved"


@dataclass(frozen=True, slots=True)
class RunComparison:
    """Diff between two run summaries."""

    before_run_id: str
    after_run_id: str
    new: tuple[FindingRef, ...] = field(default_factory=tuple)
    resolved: tuple[FindingRef, ...] = field(default_factory=tuple)
    persistent: tuple[FindingRef, ...] = field(default_factory=tuple)
    severity_changes: tuple[SeverityChange, ...] = field(default_factory=tuple)
    score_delta: float | None = None
    severity_counts_before: dict[str, int] = field(default_factory=dict)
    severity_counts_after: dict[str, int] = field(default_factory=dict)

    @property
    def has_regressions(self) -> bool:
        return bool(self.new) or any(c.direction == "regressed" for c in self.severity_changes)


def compare_runs(before: RunSummary, after: RunSummary) -> RunComparison:
    """Return a :class:`RunComparison` for two summaries."""

    before_by_fp: dict[tuple[str, str, str, str], FindingRef] = {
        _fingerprint(f): f for f in before.findings
    }
    after_by_fp: dict[tuple[str, str, str, str], FindingRef] = {
        _fingerprint(f): f for f in after.findings
    }

    new = tuple(
        sorted(
            (f for fp, f in after_by_fp.items() if fp not in before_by_fp),
            key=lambda f: (f.module, f.severity, f.title),
        )
    )
    resolved = tuple(
        sorted(
            (f for fp, f in before_by_fp.items() if fp not in after_by_fp),
            key=lambda f: (f.module, f.severity, f.title),
        )
    )
    persistent = tuple(
        sorted(
            (after_by_fp[fp] for fp in after_by_fp if fp in before_by_fp),
            key=lambda f: (f.module, f.severity, f.title),
        )
    )

    severity_changes: list[SeverityChange] = []
    for fp, after_finding in after_by_fp.items():
        before_finding = before_by_fp.get(fp)
        if before_finding is None:
            continue
        before_rank = _SEVERITY_ORDER.get(before_finding.severity, 0)
        after_rank = _SEVERITY_ORDER.get(after_finding.severity, 0)
        if after_rank > before_rank:
            severity_changes.append(
                SeverityChange(
                    before=before_finding,
                    after=after_finding,
                    direction="regressed",
                )
            )
        elif after_rank < before_rank:
            severity_changes.append(
                SeverityChange(
                    before=before_finding,
                    after=after_finding,
                    direction="improved",
                )
            )

    score_delta: float | None = None
    if before.quality_score is not None and after.quality_score is not None:
        score_delta = round(after.quality_score - before.quality_score, 2)

    return RunComparison(
        before_run_id=before.run_id,
        after_run_id=after.run_id,
        new=new,
        resolved=resolved,
        persistent=persistent,
        severity_changes=tuple(severity_changes),
        score_delta=score_delta,
        severity_counts_before=severity_breakdown(before),
        severity_counts_after=severity_breakdown(after),
    )


__all__ = [
    "RunComparison",
    "SeverityChange",
    "compare_runs",
]
