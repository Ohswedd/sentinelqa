"""Trend rendering across local run history (, ).

Reads recent runs from ``.sentinel/runs/<id>/`` (the canonical artifact
tree, our engineering rules) and derives a small set of headline series:

- Total quality score over time.
- Per-module pass rate over time.
- Top recurring finding IDs.

We deliberately stay local: no external storage, no telemetry.
cloud comes later (our product spec — no telemetry by default). The renderer
emits a small inline SVG sparkline per series so the HTML report stays
JavaScript-free for charting.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from engine.domain.finding import Severity
from engine.reporter.markdown_writer import SEVERITY_LABEL

_DEFAULT_HISTORY_DEPTH: Final[int] = 10
_SPARKLINE_WIDTH: Final[int] = 200
_SPARKLINE_HEIGHT: Final[int] = 48
_SPARKLINE_PAD: Final[int] = 4
_TOP_RECURRING_LIMIT: Final[int] = 5


@dataclass(frozen=True)
class TrendPoint:
    """One run's contribution to a series."""

    run_id: str
    started_at: str
    value: float


@dataclass(frozen=True)
class ModulePassRateSeries:
    """Pass-rate trend for a single module."""

    module: str
    points: tuple[TrendPoint, ...]

    @property
    def latest_display(self) -> str:
        if not self.points:
            return "n/a"
        return f"{self.points[-1].value:.0%}"

    @property
    def sparkline_svg(self) -> str:
        values = [p.value for p in self.points]
        return _render_sparkline(values, ymin=0.0, ymax=1.0)


@dataclass(frozen=True)
class TopRecurring:
    """Recurring finding seen across recent runs."""

    finding_id: str
    title: str
    severity: Severity
    count: int


@dataclass
class TrendData:
    """Aggregated trends across recent runs (most recent last)."""

    score_series: tuple[TrendPoint, ...] = ()
    module_pass_rates: dict[str, ModulePassRateSeries] = field(default_factory=dict)
    top_recurring: tuple[TopRecurring, ...] = ()

    def is_visible(self) -> bool:
        # Render only when we have at least one prior run to compare
        # against (our product spec — trends only when history exists).
        return len(self.score_series) >= 2

    def to_template_context(self) -> Mapping[str, Any]:
        scores = [p.value for p in self.score_series]
        latest = self.score_series[-1].value if self.score_series else None
        previous = self.score_series[-2].value if len(self.score_series) >= 2 else None
        return {
            "score_series": list(self.score_series),
            "score_sparkline_svg": _render_sparkline(scores, ymin=0.0, ymax=100.0),
            "latest_score": "n/a" if latest is None else f"{latest:.1f}",
            "previous_score": "n/a" if previous is None else f"{previous:.1f}",
            "module_pass_rates": [
                (name, series) for name, series in sorted(self.module_pass_rates.items())
            ],
            "top_recurring": [
                {
                    "finding_id": entry.finding_id,
                    "title": entry.title,
                    "severity": entry.severity,
                    "severity_label": SEVERITY_LABEL[entry.severity],
                    "count": entry.count,
                }
                for entry in self.top_recurring
            ],
        }


def compute_trends(
    runs_root: Path,
    *,
    current_run_id: str | None = None,
    history_depth: int = _DEFAULT_HISTORY_DEPTH,
) -> TrendData:
    """Walk ``runs_root`` (newest-first) and build a :class:`TrendData`.

    ``current_run_id`` is included in the series if present on disk.
    Missing or malformed JSON files are skipped silently — trends are
    best-effort, not a gate.
    """

    if not runs_root.exists():
        return TrendData()

    run_dirs: list[Path] = []
    for entry in runs_root.iterdir():
        if not entry.is_dir() or entry.name == "latest":
            continue
        run_dirs.append(entry)

    snapshots: list[_RunSnapshot] = []
    for run_dir in run_dirs:
        snap = _load_snapshot(run_dir)
        if snap is not None:
            snapshots.append(snap)
    snapshots.sort(key=lambda s: (s.started_at, s.run_id))
    if history_depth > 0:
        snapshots = snapshots[-history_depth:]

    score_series = tuple(
        TrendPoint(run_id=s.run_id, started_at=s.started_at, value=s.score)
        for s in snapshots
        if s.score is not None
    )

    module_pass_rates = _module_pass_rate_series(snapshots)
    top_recurring = _top_recurring(snapshots)

    return TrendData(
        score_series=score_series,
        module_pass_rates=module_pass_rates,
        top_recurring=top_recurring,
    )


@dataclass(frozen=True)
class _RunSnapshot:
    run_id: str
    started_at: str
    status: str
    score: float | None
    module_results: tuple[Mapping[str, Any], ...]
    findings: tuple[Mapping[str, Any], ...]


def _load_snapshot(run_dir: Path) -> _RunSnapshot | None:
    run_json = run_dir / "run.json"
    if not run_json.exists():
        return None
    try:
        run_payload: dict[str, Any] = json.loads(run_json.read_text(encoding="utf-8"))
    except ValueError:
        return None

    findings_payload: list[Mapping[str, Any]] = []
    findings_path = run_dir / "findings.json"
    if findings_path.exists():
        try:
            doc = json.loads(findings_path.read_text(encoding="utf-8"))
            findings_payload = list(doc.get("findings", []))
        except ValueError:
            findings_payload = []

    module_results: list[Mapping[str, Any]] = []
    # `run.json` doesn't currently embed module results, so we read
    # them from the per-module folder if available. writes
    # `module-results/<module>.json`; we tolerate the directory being
    # missing for older runs.
    module_dir = run_dir / "module-results"
    if module_dir.is_dir():
        for path in sorted(module_dir.glob("*.json")):
            try:
                module_results.append(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                continue

    return _RunSnapshot(
        run_id=str(run_payload.get("run_id", run_dir.name)),
        started_at=str(run_payload.get("started_at", "")),
        status=str(run_payload.get("status", "")),
        score=_coerce_score(run_payload.get("quality_score")),
        module_results=tuple(module_results),
        findings=tuple(findings_payload),
    )


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _module_pass_rate_series(
    snapshots: Sequence[_RunSnapshot],
) -> dict[str, ModulePassRateSeries]:
    by_module: dict[str, list[TrendPoint]] = {}
    for snap in snapshots:
        if not snap.module_results:
            continue
        per: dict[str, tuple[int, int]] = {}
        for entry in snap.module_results:
            module = str(entry.get("name", "")).strip() or str(entry.get("module", "")).strip()
            if not module:
                continue
            status = str(entry.get("status", ""))
            passed, total = per.get(module, (0, 0))
            total += 1
            if status == "passed":
                passed += 1
            per[module] = (passed, total)
        for module, (passed, total) in per.items():
            rate = (passed / total) if total else 0.0
            by_module.setdefault(module, []).append(
                TrendPoint(run_id=snap.run_id, started_at=snap.started_at, value=rate)
            )
    return {
        module: ModulePassRateSeries(module=module, points=tuple(points))
        for module, points in by_module.items()
    }


def _top_recurring(snapshots: Sequence[_RunSnapshot]) -> tuple[TopRecurring, ...]:
    counts: dict[str, int] = {}
    titles: dict[str, str] = {}
    severities: dict[str, Severity] = {}
    for snap in snapshots:
        for f in snap.findings:
            fid = str(f.get("id", "")).strip()
            if not fid:
                continue
            counts[fid] = counts.get(fid, 0) + 1
            titles.setdefault(fid, str(f.get("title", fid)))
            sev_value = f.get("severity")
            if isinstance(sev_value, str) and sev_value in SEVERITY_LABEL:
                severities.setdefault(fid, sev_value)  # type: ignore[arg-type]
    out: list[TopRecurring] = []
    for fid, count in counts.items():
        if count < 2:
            continue
        out.append(
            TopRecurring(
                finding_id=fid,
                title=titles.get(fid, fid),
                severity=severities.get(fid, "info"),
                count=count,
            )
        )
    out.sort(key=lambda e: (-e.count, e.finding_id))
    return tuple(out[:_TOP_RECURRING_LIMIT])


def _render_sparkline(
    values: Sequence[float],
    *,
    ymin: float,
    ymax: float,
) -> str:
    """Return a self-contained SVG sparkline for ``values``.

    Empty / single-point series produce an empty `<svg/>` rather than
    an axis-only chart — the template hides the section when ``values``
    is empty.
    """

    if not values:
        return (
            f'<svg class="sparkline" viewBox="0 0 {_SPARKLINE_WIDTH} '
            f'{_SPARKLINE_HEIGHT}" aria-hidden="true"></svg>'
        )
    span = max(ymax - ymin, 1e-9)
    width = _SPARKLINE_WIDTH - 2 * _SPARKLINE_PAD
    height = _SPARKLINE_HEIGHT - 2 * _SPARKLINE_PAD
    if len(values) == 1:
        x = _SPARKLINE_PAD + width / 2
        y = _project_y(values[0], ymin, span, height)
        return (
            f'<svg class="sparkline" viewBox="0 0 {_SPARKLINE_WIDTH} {_SPARKLINE_HEIGHT}" '
            f'aria-hidden="true">'
            f'<circle class="sparkline-dot" cx="{x:.2f}" cy="{y:.2f}" r="2.5"/></svg>'
        )
    step = width / (len(values) - 1)
    pts: list[str] = []
    for i, v in enumerate(values):
        x = _SPARKLINE_PAD + i * step
        y = _project_y(v, ymin, span, height)
        pts.append(f"{x:.2f},{y:.2f}")
    last_x, last_y = pts[-1].split(",")
    path = " ".join(pts)
    return (
        f'<svg class="sparkline" viewBox="0 0 {_SPARKLINE_WIDTH} {_SPARKLINE_HEIGHT}" '
        f'aria-hidden="true">'
        f'<polyline class="sparkline-path" points="{path}"/>'
        f'<circle class="sparkline-dot" cx="{last_x}" cy="{last_y}" r="2.5"/></svg>'
    )


def _project_y(value: float, ymin: float, span: float, height: int) -> float:
    pct = (float(value) - ymin) / span
    pct = max(0.0, min(1.0, pct))
    return _SPARKLINE_PAD + (1.0 - pct) * height


def iter_started_at(snapshots: Iterable[_RunSnapshot]) -> Iterable[datetime]:
    """Helper retained for tests to compare canonical ordering."""

    for snap in snapshots:
        try:
            yield datetime.fromisoformat(snap.started_at)
        except ValueError:
            continue


__all__ = [
    "ModulePassRateSeries",
    "TopRecurring",
    "TrendData",
    "TrendPoint",
    "compute_trends",
]
