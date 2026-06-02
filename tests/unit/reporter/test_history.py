# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the trends + status snapshot helpers."""

from __future__ import annotations

import json
from pathlib import Path

from engine.reporter.history import (
    HistorySeries,
    StatusSnapshot,
    compute_history_series,
    compute_status_snapshot,
    iter_run_dirs,
    render_status_widget_js,
)


def _write_run(
    parent: Path,
    *,
    run_id: str,
    started_at: str,
    status: str = "passed",
    quality: float | None = 90.0,
    findings: list[dict] | None = None,
) -> None:
    run_dir = parent / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_payload: dict[str, object] = {
        "run_id": run_id,
        "status": status,
        "modules_run": ["security"],
        "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
        "started_at": started_at,
        "finished_at": started_at,
    }
    if quality is not None:
        run_payload["quality_score"] = quality
    (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
    (run_dir / "findings.json").write_text(
        json.dumps({"findings": findings or []}), encoding="utf-8"
    )


def test_iter_run_dirs_skips_non_run_entries(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", started_at="2026-06-01T00:00:00+00:00")
    (tmp_path / "latest").mkdir()
    (tmp_path / "scratch").mkdir()
    (tmp_path / "random.txt").write_text("x", encoding="utf-8")
    dirs = iter_run_dirs(tmp_path)
    names = {d.name for d in dirs}
    assert names == {"RUN-XAAAAAAAAAAA"}


def test_iter_run_dirs_returns_empty_for_missing_root(tmp_path: Path) -> None:
    assert iter_run_dirs(tmp_path / "nope") == ()


def test_compute_history_series_returns_chronological_order(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", started_at="2026-06-01T00:00:00+00:00")
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAB", started_at="2026-06-02T00:00:00+00:00")
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAC", started_at="2026-06-03T00:00:00+00:00")
    series = compute_history_series(tmp_path)
    assert isinstance(series, HistorySeries)
    assert [p.run_id for p in series.points] == [
        "RUN-XAAAAAAAAAAA",
        "RUN-XAAAAAAAAAAB",
        "RUN-XAAAAAAAAAAC",
    ]


def test_compute_history_series_honours_window(tmp_path: Path) -> None:
    for i in range(15):
        _write_run(
            tmp_path,
            run_id=f"RUN-XAAAAAAAA{i:03d}",
            started_at=f"2026-06-{i + 1:02d}T00:00:00+00:00",
        )
    series = compute_history_series(tmp_path, window=5)
    assert len(series.points) == 5
    assert series.points[-1].run_id == "RUN-XAAAAAAAA014"


def test_compute_history_series_records_severity_counts(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        run_id="RUN-XAAAAAAAAAAA",
        started_at="2026-06-01T00:00:00+00:00",
        findings=[
            {"id": "FND-1", "severity": "high"},
            {"id": "FND-2", "severity": "medium"},
            {"id": "FND-3", "severity": "medium"},
        ],
    )
    series = compute_history_series(tmp_path)
    assert series.points[-1].findings_by_severity["medium"] == 2


def test_compute_history_series_handles_missing_score(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        run_id="RUN-XAAAAAAAAAAA",
        started_at="2026-06-01T00:00:00+00:00",
        quality=None,
    )
    series = compute_history_series(tmp_path)
    assert series.points[-1].quality_score is None


def test_compute_status_snapshot_returns_none_when_empty(tmp_path: Path) -> None:
    assert compute_status_snapshot(tmp_path) is None


def test_compute_status_snapshot_reports_pass_above_threshold(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        run_id="RUN-XAAAAAAAAAAA",
        started_at="2026-06-01T00:00:00+00:00",
        quality=92.0,
    )
    snapshot = compute_status_snapshot(tmp_path, threshold=80.0)
    assert isinstance(snapshot, StatusSnapshot)
    assert snapshot.release_decision == "pass"
    assert snapshot.quality_score == 92.0


def test_compute_status_snapshot_reports_blocked_below_threshold(
    tmp_path: Path,
) -> None:
    _write_run(
        tmp_path,
        run_id="RUN-XAAAAAAAAAAA",
        started_at="2026-06-01T00:00:00+00:00",
        quality=40.0,
        status="failed",
    )
    snapshot = compute_status_snapshot(tmp_path, threshold=80.0)
    assert snapshot is not None
    assert snapshot.release_decision == "blocked"


def test_compute_status_snapshot_reports_unsafe_target(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        run_id="RUN-XAAAAAAAAAAA",
        started_at="2026-06-01T00:00:00+00:00",
        quality=None,
        status="unsafe_blocked",
    )
    snapshot = compute_status_snapshot(tmp_path)
    assert snapshot is not None
    assert snapshot.release_decision == "unsafe_target_rejected"


def test_render_status_widget_js_returns_executable_text() -> None:
    js = render_status_widget_js()
    assert "fetch" in js
    assert "data-endpoint" in js or "dataset.endpoint" in js
