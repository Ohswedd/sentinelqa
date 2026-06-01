# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the run-summary / compare / coverage primitives."""

from __future__ import annotations

import json
from pathlib import Path

from engine.runs import (
    RunComparison,
    RunSummary,
    compare_runs,
    find_coverage_gaps,
    load_run_summary,
)
from engine.runs.summary import severity_breakdown


def _write_run(
    run_dir: Path,
    *,
    run_id: str,
    status: str = "passed",
    quality: float = 90.0,
    findings: list[dict] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": status,
                "quality_score": quality,
                "modules_run": ["functional", "security"],
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
                "summary": {"passed": 5, "failed": 0, "blocked": 0, "info": 1},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "findings.json").write_text(
        json.dumps({"findings": findings or []}),
        encoding="utf-8",
    )
    (run_dir / "score.json").write_text(json.dumps({}), encoding="utf-8")


def _finding(**kwargs) -> dict:
    base = {
        "id": "FND-XXXXXXXXAAAA",
        "module": "security",
        "category": "headers",
        "severity": "medium",
        "title": "CSP header missing",
        "evidence": {"rule_id": "SEC-HEADERS-CSP-MISSING"},
    }
    base.update(kwargs)
    return base


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #


def test_load_run_summary_returns_normalised_view(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        run_id="RUN-XAAAAAAAAAAA",
        findings=[_finding(), _finding(id="FND-XAAAAAAAAAAB", severity="high")],
    )
    summary = load_run_summary(tmp_path)
    assert summary.run_id == "RUN-XAAAAAAAAAAA"
    assert summary.status == "passed"
    assert summary.quality_score == 90.0
    assert "functional" in summary.modules_run
    assert len(summary.findings) == 2
    assert summary.target_host == "app.example.com"


def test_load_run_summary_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    summary = load_run_summary(missing)
    assert summary.run_id == "nope"
    assert summary.findings == ()
    assert summary.quality_score is None


def test_load_run_summary_extracts_rule_code(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAB", findings=[_finding()])
    summary = load_run_summary(tmp_path)
    assert summary.findings[0].code == "SEC-HEADERS-CSP-MISSING"


def test_severity_breakdown_counts_each_level() -> None:
    summary = RunSummary(
        run_id="r",
        status="passed",
        quality_score=80.0,
        modules_run=(),
        findings=(),
    )
    counts = severity_breakdown(summary)
    assert counts == {}


# --------------------------------------------------------------------------- #
# Compare
# --------------------------------------------------------------------------- #


def test_compare_runs_detects_new_finding(tmp_path: Path) -> None:
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_run(before_dir, run_id="RUN-BEFOREAAAAA", findings=[])
    _write_run(after_dir, run_id="RUN-AFTERRAAAAA", findings=[_finding()])
    diff = compare_runs(load_run_summary(before_dir), load_run_summary(after_dir))
    assert isinstance(diff, RunComparison)
    assert len(diff.new) == 1
    assert diff.resolved == ()
    assert diff.has_regressions is True


def test_compare_runs_detects_resolved_finding(tmp_path: Path) -> None:
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_run(before_dir, run_id="r1", findings=[_finding()])
    _write_run(after_dir, run_id="r2", findings=[])
    diff = compare_runs(load_run_summary(before_dir), load_run_summary(after_dir))
    assert len(diff.resolved) == 1
    assert diff.new == ()
    assert diff.has_regressions is False


def test_compare_runs_detects_severity_regression(tmp_path: Path) -> None:
    before_dir = tmp_path / "b"
    after_dir = tmp_path / "a"
    _write_run(before_dir, run_id="r1", findings=[_finding(severity="low")])
    _write_run(after_dir, run_id="r2", findings=[_finding(severity="high")])
    diff = compare_runs(load_run_summary(before_dir), load_run_summary(after_dir))
    assert any(c.direction == "regressed" for c in diff.severity_changes)


def test_compare_runs_detects_severity_improvement(tmp_path: Path) -> None:
    before_dir = tmp_path / "b"
    after_dir = tmp_path / "a"
    _write_run(before_dir, run_id="r1", findings=[_finding(severity="critical")])
    _write_run(after_dir, run_id="r2", findings=[_finding(severity="low")])
    diff = compare_runs(load_run_summary(before_dir), load_run_summary(after_dir))
    assert any(c.direction == "improved" for c in diff.severity_changes)


def test_compare_runs_computes_score_delta(tmp_path: Path) -> None:
    before_dir = tmp_path / "b"
    after_dir = tmp_path / "a"
    _write_run(before_dir, run_id="r1", quality=80.0, findings=[])
    _write_run(after_dir, run_id="r2", quality=85.0, findings=[])
    diff = compare_runs(load_run_summary(before_dir), load_run_summary(after_dir))
    assert diff.score_delta == 5.0


def test_compare_runs_handles_persistent_findings(tmp_path: Path) -> None:
    before_dir = tmp_path / "b"
    after_dir = tmp_path / "a"
    _write_run(before_dir, run_id="r1", findings=[_finding()])
    _write_run(after_dir, run_id="r2", findings=[_finding()])
    diff = compare_runs(load_run_summary(before_dir), load_run_summary(after_dir))
    assert len(diff.persistent) == 1
    assert diff.new == ()
    assert diff.resolved == ()


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #


def test_find_coverage_gaps_returns_uncovered_routes() -> None:
    payload = {
        "graph": {
            "routes": [
                {"path": "/", "auth_required": False},
                {"path": "/dashboard", "auth_required": True},
            ]
        },
        "forms": [],
        "api_endpoints": [],
    }
    report = find_coverage_gaps(payload, covered_routes=["/"])
    assert report.coverage_ratio == 0.5
    assert len(report.gaps) == 1
    assert report.gaps[0].identifier == "/dashboard"
    assert report.gaps[0].risk_score == 4


def test_find_coverage_gaps_ranks_by_risk_descending() -> None:
    payload = {
        "graph": {
            "routes": [
                {"path": "/static.css", "static_asset": True},
                {"path": "/admin", "auth_required": True, "hot_path": True},
            ]
        },
    }
    report = find_coverage_gaps(payload)
    assert report.gaps[0].identifier == "/admin"
    assert report.gaps[0].risk_score >= 4


def test_find_coverage_gaps_handles_forms() -> None:
    payload = {
        "forms": [
            {"id": "login", "contains_credentials": True, "method": "POST"},
            {"id": "search", "method": "GET"},
        ]
    }
    report = find_coverage_gaps(payload, covered_forms=["search"])
    assert any(g.identifier == "login" and g.risk_score == 4 for g in report.gaps)


def test_find_coverage_gaps_handles_api_endpoints() -> None:
    payload = {
        "api_endpoints": [
            {"method": "POST", "path": "/api/users"},
            {"method": "GET", "path": "/api/health"},
        ]
    }
    report = find_coverage_gaps(payload, covered_api_endpoints=["GET /api/health"])
    assert len(report.gaps) == 1
    assert "POST" in report.gaps[0].identifier
    assert report.gaps[0].risk_score == 3


def test_find_coverage_gaps_returns_full_coverage_when_all_match() -> None:
    payload = {"graph": {"routes": [{"path": "/", "auth_required": False}]}}
    report = find_coverage_gaps(payload, covered_routes=["/"])
    assert report.gaps == ()
    assert report.coverage_ratio == 1.0


def test_find_coverage_gaps_empty_discovery_returns_full_coverage() -> None:
    report = find_coverage_gaps({}, covered_routes=[])
    assert report.discovered_total == 0
    assert report.coverage_ratio == 1.0
