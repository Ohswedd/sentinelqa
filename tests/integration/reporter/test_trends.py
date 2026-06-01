"""Trend computation across local run history."""

from __future__ import annotations

import json
from pathlib import Path

from engine.reporter.trends import (
    ModulePassRateSeries,
    TopRecurring,
    compute_trends,
)


def _write_run(
    root: Path,
    run_id: str,
    *,
    started_at: str,
    quality_score: float | None,
    modules: list[dict[str, object]] | None = None,
    findings: list[dict[str, object]] | None = None,
) -> None:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_payload = {
        "run_id": run_id,
        "started_at": started_at,
        "status": "passed",
        "quality_score": quality_score,
    }
    (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
    if findings is not None:
        (run_dir / "findings.json").write_text(json.dumps({"findings": findings}), encoding="utf-8")
    if modules is not None:
        modules_dir = run_dir / "module-results"
        modules_dir.mkdir(exist_ok=True)
        for module_payload in modules:
            name = str(module_payload.get("name", "module"))
            (modules_dir / f"{name}.json").write_text(json.dumps(module_payload), encoding="utf-8")


def test_trends_hidden_with_no_history(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    runs_root.mkdir(parents=True)
    trends = compute_trends(runs_root)
    assert trends.is_visible() is False
    assert trends.score_series == ()
    assert trends.module_pass_rates == {}


def test_trends_hidden_with_one_run(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    _write_run(
        runs_root, "RUN-AAAAAAAAAAAA", started_at="2026-05-27T12:00:00+00:00", quality_score=80.0
    )
    trends = compute_trends(runs_root)
    assert len(trends.score_series) == 1
    assert trends.is_visible() is False


def test_trends_score_series_chronological(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    _write_run(
        runs_root, "RUN-CCCCCCCCCCCC", started_at="2026-05-27T13:00:00+00:00", quality_score=92.0
    )
    _write_run(
        runs_root, "RUN-AAAAAAAAAAAA", started_at="2026-05-27T11:00:00+00:00", quality_score=80.0
    )
    _write_run(
        runs_root, "RUN-BBBBBBBBBBBB", started_at="2026-05-27T12:00:00+00:00", quality_score=85.0
    )
    trends = compute_trends(runs_root)
    assert [p.run_id for p in trends.score_series] == [
        "RUN-AAAAAAAAAAAA",
        "RUN-BBBBBBBBBBBB",
        "RUN-CCCCCCCCCCCC",
    ]
    assert [p.value for p in trends.score_series] == [80.0, 85.0, 92.0]
    assert trends.is_visible() is True


def test_trends_module_pass_rates(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    _write_run(
        runs_root,
        "RUN-AAAAAAAAAAAA",
        started_at="2026-05-27T11:00:00+00:00",
        quality_score=80.0,
        modules=[
            {"name": "functional", "status": "passed"},
            {"name": "security", "status": "failed"},
        ],
    )
    _write_run(
        runs_root,
        "RUN-BBBBBBBBBBBB",
        started_at="2026-05-27T12:00:00+00:00",
        quality_score=90.0,
        modules=[
            {"name": "functional", "status": "passed"},
            {"name": "security", "status": "passed"},
        ],
    )
    trends = compute_trends(runs_root)
    series = trends.module_pass_rates["security"]
    assert isinstance(series, ModulePassRateSeries)
    assert [p.value for p in series.points] == [0.0, 1.0]
    assert series.latest_display == "100%"


def test_trends_top_recurring_findings(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    finding: dict[str, object] = {
        "id": "FND-RECURAAAAAAA",
        "title": "Same finding again",
        "severity": "high",
    }
    _write_run(
        runs_root,
        "RUN-AAAAAAAAAAAA",
        started_at="2026-05-27T11:00:00+00:00",
        quality_score=80.0,
        findings=[finding],
    )
    _write_run(
        runs_root,
        "RUN-BBBBBBBBBBBB",
        started_at="2026-05-27T12:00:00+00:00",
        quality_score=82.0,
        findings=[finding],
    )
    trends = compute_trends(runs_root)
    assert trends.top_recurring == (
        TopRecurring(
            finding_id="FND-RECURAAAAAAA",
            title="Same finding again",
            severity="high",
            count=2,
        ),
    )


def test_trends_skip_latest_pointer(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    _write_run(
        runs_root, "RUN-AAAAAAAAAAAA", started_at="2026-05-27T11:00:00+00:00", quality_score=80.0
    )
    latest_dir = runs_root / "latest"
    latest_dir.mkdir()
    (latest_dir / "run.json").write_text(json.dumps({"run_id": "shouldignore"}), encoding="utf-8")
    trends = compute_trends(runs_root)
    assert [p.run_id for p in trends.score_series] == ["RUN-AAAAAAAAAAAA"]


def test_trends_handles_corrupt_run_json(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    _write_run(
        runs_root, "RUN-AAAAAAAAAAAA", started_at="2026-05-27T11:00:00+00:00", quality_score=80.0
    )
    bad = runs_root / "RUN-BADAAAAAAAAA"
    bad.mkdir()
    (bad / "run.json").write_text("not valid json", encoding="utf-8")
    trends = compute_trends(runs_root)
    # Corrupt run is dropped; valid one remains.
    assert len(trends.score_series) == 1
    assert trends.score_series[0].run_id == "RUN-AAAAAAAAAAAA"


def test_trends_sparkline_svg_is_inline(tmp_path: Path) -> None:
    runs_root = tmp_path / ".sentinel" / "runs"
    for i, score in enumerate([80.0, 85.0, 90.0]):
        _write_run(
            runs_root,
            f"RUN-{chr(65 + i) * 12}",
            started_at=f"2026-05-27T1{i}:00:00+00:00",
            quality_score=score,
        )
    trends = compute_trends(runs_root)
    ctx = trends.to_template_context()
    assert "<svg" in ctx["score_sparkline_svg"]
    assert "polyline" in ctx["score_sparkline_svg"]
    # No external attribute references.
    assert "http" not in ctx["score_sparkline_svg"]
