# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Run-history timeseries + status snapshot (v1.6.0).

Two helpers that walk ``.sentinel/runs/<run-id>/`` and produce:

* :func:`compute_history_series` — a bounded time-ordered series
  the run viewer renders as inline Chart.js graphs. Per-point
  payload includes the run id, started_at, quality_score, status,
  and per-severity finding counts.
* :func:`compute_status_snapshot` — the compact
  ``/api/status.json`` payload the public status-page widget
  consumes.

Sits next to the existing :mod:`engine.reporter.trends` (which
focuses on per-module SVG sparklines for the static HTML report);
this module produces the JSON timeseries the runtime viewer needs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

_DEFAULT_WINDOW: Final[int] = 90


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    """One point in a history timeseries."""

    run_id: str
    started_at: str  # ISO-8601
    quality_score: float | None
    status: str
    findings_by_severity: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HistorySeries:
    """A bounded, time-ordered series of run points."""

    points: tuple[HistoryPoint, ...]
    window: int

    @property
    def last(self) -> HistoryPoint | None:
        return self.points[-1] if self.points else None


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """The compact ``/api/status.json`` payload."""

    run_id: str
    status: str
    quality_score: float | None
    release_decision: str
    updated_at: str
    findings_by_severity: dict[str, int] = field(default_factory=dict)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _severity_counts(findings_payload: dict[str, Any] | None) -> dict[str, int]:
    if not findings_payload:
        return {}
    rows = findings_payload.get("findings")
    if not isinstance(rows, list):
        return {}
    out: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sev = str(row.get("severity", "info"))
        out[sev] = out.get(sev, 0) + 1
    return out


def _read_point(run_dir: Path) -> HistoryPoint | None:
    run_payload = _load_json(run_dir / "run.json")
    if run_payload is None:
        return None
    findings_payload = _load_json(run_dir / "findings.json")
    quality = run_payload.get("quality_score")
    return HistoryPoint(
        run_id=str(run_payload.get("run_id", run_dir.name)),
        started_at=str(run_payload.get("started_at", "")),
        quality_score=(float(quality) if isinstance(quality, int | float) else None),
        status=str(run_payload.get("status", "")),
        findings_by_severity=_severity_counts(findings_payload),
    )


def iter_run_dirs(runs_root: Path) -> tuple[Path, ...]:
    """Return every direct child of ``runs_root`` shaped like a run dir."""

    if not runs_root.is_dir():
        return ()
    out: list[Path] = []
    for entry in runs_root.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == "latest":
            # The latest pointer may be a separate dir on Windows; we
            # walk only the canonical run dirs.
            continue
        if not entry.name.startswith("RUN-"):
            continue
        out.append(entry)
    return tuple(out)


def compute_history_series(runs_root: Path, *, window: int = _DEFAULT_WINDOW) -> HistorySeries:
    """Walk ``runs_root`` and return the most-recent ``window`` runs sorted."""

    points: list[HistoryPoint] = []
    for run_dir in iter_run_dirs(runs_root):
        point = _read_point(run_dir)
        if point is not None:
            points.append(point)
    points.sort(key=lambda p: p.started_at)
    if len(points) > window:
        points = points[-window:]
    return HistorySeries(points=tuple(points), window=window)


def _release_decision_for(status: str, score: float | None, threshold: float) -> str:
    if status == "unsafe_blocked":
        return "unsafe_target_rejected"
    if status in {"dry_run", "incomplete"}:
        return "inconclusive"
    if score is None:
        return "inconclusive"
    return "pass" if score >= threshold else "blocked"


def compute_status_snapshot(runs_root: Path, *, threshold: float = 80.0) -> StatusSnapshot | None:
    """Build the `/api/status.json` payload from the most-recent run."""

    series = compute_history_series(runs_root)
    last = series.last
    if last is None:
        return None
    decision = _release_decision_for(last.status, last.quality_score, threshold)
    return StatusSnapshot(
        run_id=last.run_id,
        status=last.status,
        quality_score=last.quality_score,
        release_decision=decision,
        updated_at=last.started_at,
        findings_by_severity=dict(last.findings_by_severity),
    )


def render_status_widget_js() -> str:
    """Return a tiny embeddable ``widget.js`` for a public status page.

    The script looks for an element with a ``data-endpoint`` attribute
    immediately preceding it in the DOM, fetches the status JSON,
    and renders the latest score + release decision. Hosted by
    ``sentinel serve``.
    """

    return (
        "(()=>{const el=document.currentScript.previousElementSibling;"
        "if(!el||!el.dataset.endpoint)return;"
        "fetch(el.dataset.endpoint).then(r=>r.json()).then(d=>{"
        "el.textContent=`SentinelQA: ${d.quality_score==null?'(no score)':d.quality_score} `"
        "+`(${(d.release_decision||'').toUpperCase()})`;"
        "el.dataset.score=d.quality_score;"
        "el.dataset.decision=d.release_decision;"
        "}).catch(()=>{el.textContent='SentinelQA: unreachable';});})();"
    )


__all__ = [
    "HistoryPoint",
    "HistorySeries",
    "StatusSnapshot",
    "compute_history_series",
    "compute_status_snapshot",
    "iter_run_dirs",
    "render_status_widget_js",
]
