# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the run-to-run diff module."""

from __future__ import annotations

import json
from pathlib import Path

from engine.reporter.run_diff import (
    ArtifactDelta,
    RunDiff,
    compute_run_diff,
    render_run_diff_section,
)


def _write_run(
    run_dir: Path,
    *,
    run_id: str,
    quality: float = 90.0,
    findings: list[dict] | None = None,
    with_plan: bool = False,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "passed",
                "quality_score": quality,
                "modules_run": ["security"],
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
                "summary": {"passed": 1, "failed": 0, "blocked": 0, "info": 0},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "findings.json").write_text(
        json.dumps({"findings": findings or []}), encoding="utf-8"
    )
    (run_dir / "score.json").write_text("{}", encoding="utf-8")
    if with_plan:
        (run_dir / "plan.json").write_text(json.dumps({"modules": ["security"]}), encoding="utf-8")


def _finding(severity: str = "medium", title: str = "CSP missing") -> dict:
    return {
        "id": "FND-XAAAAAAAAAAA",
        "module": "security",
        "category": "headers",
        "severity": severity,
        "title": title,
        "evidence": {"rule_id": "SEC-HEADERS-CSP-MISSING"},
    }


def test_compute_run_diff_handles_identical_runs(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_run(before, run_id="RUN-BEFOREAAAAA", findings=[_finding()])
    _write_run(after, run_id="RUN-AFTERRAAAAA", findings=[_finding()])
    diff = compute_run_diff(before, after)
    assert isinstance(diff, RunDiff)
    assert diff.comparison.new == ()
    assert diff.comparison.resolved == ()
    assert diff.has_changes is False


def test_compute_run_diff_detects_new_findings(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_run(before, run_id="RUN-BEFOREAAAAA", findings=[])
    _write_run(after, run_id="RUN-AFTERRAAAAA", findings=[_finding(severity="high")])
    diff = compute_run_diff(before, after)
    assert len(diff.comparison.new) == 1
    assert diff.has_changes is True


def test_compute_run_diff_detects_resolved_findings(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_run(before, run_id="RUN-BEFOREAAAAA", findings=[_finding()])
    _write_run(after, run_id="RUN-AFTERRAAAAA", findings=[])
    diff = compute_run_diff(before, after)
    assert len(diff.comparison.resolved) == 1


def test_compute_run_diff_reports_artifact_size_delta(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_run(before, run_id="RUN-BEFOREAAAAA", findings=[])
    _write_run(after, run_id="RUN-AFTERRAAAAA", findings=[_finding()], with_plan=True)
    diff = compute_run_diff(before, after)
    plan_delta = next((d for d in diff.artifact_deltas if d.artifact == "plan.json"), None)
    assert plan_delta is not None
    assert plan_delta.changed is True
    assert plan_delta.before_bytes == 0
    assert plan_delta.after_bytes > 0


def test_compute_run_diff_skips_artifacts_absent_from_both(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_run(before, run_id="r1")
    _write_run(after, run_id="r2")
    diff = compute_run_diff(before, after)
    names = {d.artifact for d in diff.artifact_deltas}
    assert "discovery.json" not in names  # never written → skipped


def test_render_run_diff_section_handles_clean_diff(tmp_path: Path) -> None:
    before = tmp_path / "b"
    after = tmp_path / "a"
    _write_run(before, run_id="RUN-BEFOREAAAAA")
    _write_run(after, run_id="RUN-AFTERRAAAAA")
    diff = compute_run_diff(before, after)
    html = render_run_diff_section(diff)
    assert "run-diff-clean" in html
    assert "No findings or artifacts changed" in html


def test_render_run_diff_section_shows_score_delta(tmp_path: Path) -> None:
    before = tmp_path / "b"
    after = tmp_path / "a"
    _write_run(before, run_id="RUN-BEFOREAAAAA", quality=80.0, findings=[_finding()])
    _write_run(after, run_id="RUN-AFTERRAAAAA", quality=70.0, findings=[])
    diff = compute_run_diff(before, after)
    html = render_run_diff_section(diff)
    assert "-10.0" in html
    assert "Resolved" in html


def test_render_run_diff_section_escapes_run_ids(tmp_path: Path) -> None:
    before = tmp_path / "b"
    after = tmp_path / "a"
    _write_run(before, run_id="RUN-BEFOREAAAAA")
    _write_run(
        after,
        run_id="RUN-AFTERRAAAAA",
        findings=[_finding(title="<script>alert(1)</script>")],
    )
    diff = compute_run_diff(before, after)
    html = render_run_diff_section(diff)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_artifact_delta_is_a_value_object() -> None:
    delta = ArtifactDelta(artifact="run.json", before_bytes=10, after_bytes=20, changed=True)
    assert delta.artifact == "run.json"
    assert delta.changed is True
