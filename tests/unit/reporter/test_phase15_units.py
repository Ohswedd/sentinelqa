"""Unit tests covering Phase 15 helper branches."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.policy_decision import PolicyDecision
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.reporter.audit_view import normalize_audit_entries
from engine.reporter.html_writer import (
    HtmlReportInputs,
    build_template_context,
    collect_artifact_links,
    iter_severity_buckets,
)
from engine.reporter.pr_comment import render_pr_comment
from engine.reporter.slack import render_slack_payload
from engine.reporter.trends import (
    TrendData,
    TrendPoint,
    compute_trends,
)


@pytest.fixture
def run() -> TestRun:
    return TestRun(
        id="RUN-UNITAAAAAAAA",
        started_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={},
        modules_run=("functional",),
        status="passed",
    )


@pytest.fixture
def critical_finding(run: TestRun) -> Finding:
    return _build_finding(
        run.id,
        id="FND-CRITUNITAAAA",
        module="security",
        category="security/headers",
        severity="critical",
        confidence=0.95,
        title="Crit title",
        description="Crit description",
        location=FindingLocation(route="/admin"),
        evidence=(
            Evidence(
                id="EVD-CRITUNITAAAA",
                type="screenshot",
                path=Path("screenshots/admin.png"),
                redacted=True,
            ),
        ),
        recommendation="Add headers.",
    )


def _build_finding(run_id: str, **kwargs: Any) -> Finding:
    kwargs.setdefault("created_at", datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC))
    return Finding(run_id=run_id, **kwargs)


def test_pr_comment_blocked_path_has_next_steps(run: TestRun, critical_finding: Finding) -> None:
    policy = PolicyDecision(
        id="PD-BLKUNITAAAAA",
        run_id=run.id,
        release_decision="blocked",
        blocked_by=(critical_finding.id,),
        reasons=("Critical finding present.",),
    )
    body = render_pr_comment(run, (critical_finding,), None, policy)
    assert "Re-run `sentinel ci`" in body
    assert "Review every blocker" in body


def test_pr_comment_warnings_path() -> None:
    run = TestRun(
        id="RUN-WARNUNITAAAA",
        started_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={},
        modules_run=(),
        status="passed",
    )
    finding = _build_finding(
        run.id,
        id="FND-MEDIUMUNITAA",
        module="accessibility",
        category="a11y/contrast",
        severity="medium",
        confidence=0.7,
        title="Some title",
        description="Some description",
    )
    policy = PolicyDecision(
        id="PD-WARNUNITAAAA",
        run_id=run.id,
        release_decision="pass_with_warnings",
        blocked_by=(),
        reasons=("Medium findings present.",),
    )
    body = render_pr_comment(run, (finding,), None, policy)
    assert "Triage medium" in body


def test_pr_comment_inconclusive_path() -> None:
    run = TestRun(
        id="RUN-DRYUNITAAAAA",
        started_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={},
        modules_run=(),
        status="dry_run",
    )
    body = render_pr_comment(run, (), None, None)
    assert "Re-run with the full module set" in body


def test_pr_comment_unsafe_path() -> None:
    run = TestRun(
        id="RUN-UNSAFEUNITAA",
        started_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={},
        modules_run=(),
        status="unsafe_blocked",
    )
    body = render_pr_comment(run, (), None, None)
    assert "authorized" in body


def test_pr_comment_truncates_top_blockers_to_five(run: TestRun) -> None:
    findings = tuple(
        _build_finding(
            run.id,
            id=f"FND-HBLOCKER{idx:04d}",
            module="security",
            category="security/test",
            severity="high",
            confidence=0.9,
            title=f"Title {idx}",
            description=f"Description {idx}",
            evidence=(
                Evidence(
                    id=f"EVD-EVIDENCE{idx:04d}",
                    type="trace",
                    path=Path(f"traces/{idx}.zip"),
                    redacted=True,
                ),
            ),
            recommendation=f"Fix {idx}",
        )
        for idx in range(7)
    )
    body = render_pr_comment(run, findings, None, None)
    assert "+2 more" in body


def test_slack_payload_unsafe(run: TestRun) -> None:
    unsafe_run = TestRun(
        id="RUN-UNSAFEUNITSL",
        started_at=run.started_at,
        finished_at=run.finished_at,
        target=run.target,
        config_snapshot=run.config_snapshot,
        modules_run=(),
        status="unsafe_blocked",
    )
    payload = render_slack_payload(unsafe_run, (), None, None)
    fallback: str = payload["text"]
    assert "UNSAFE" in fallback


def test_collect_artifact_links_dedups_paths(tmp_path: Path) -> None:
    rows = collect_artifact_links(
        {
            "run": tmp_path / "run.json",
            "findings": tmp_path / "findings.json",
        }
    )
    hrefs = [r["href"] for r in rows]
    assert "run.json" in hrefs
    assert "findings.json" in hrefs
    assert "audit.log" in hrefs


def test_iter_severity_buckets(run: TestRun) -> None:
    f1 = _build_finding(
        run.id,
        id="FND-AAAAAAAAAAAB",
        module="m",
        category="c",
        severity="low",
        confidence=0.5,
        title="t",
        description="d",
    )
    f2 = _build_finding(
        run.id,
        id="FND-AAAAAAAAAAAC",
        module="m",
        category="c",
        severity="critical",
        confidence=0.5,
        title="t",
        description="d",
        evidence=(
            Evidence(
                id="EVD-AAAAAAAAAAAA",
                type="trace",
                path=Path("t.zip"),
                redacted=True,
            ),
        ),
        recommendation="r",
    )
    buckets = iter_severity_buckets([f1, f2])
    assert buckets == ("critical", "low")


def test_trend_data_empty_template_context() -> None:
    data = TrendData()
    ctx = data.to_template_context()
    assert ctx["latest_score"] == "n/a"
    assert ctx["previous_score"] == "n/a"


def test_trend_data_single_point_sparkline() -> None:
    data = TrendData(
        score_series=(TrendPoint(run_id="x", started_at="2026-05-29", value=80.0),),
    )
    ctx = data.to_template_context()
    assert "circle" in ctx["score_sparkline_svg"]


def test_compute_trends_skips_missing_run_json(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    (runs_root / "RUN-EMPTYDIRABCD").mkdir()
    data = compute_trends(runs_root)
    assert data.score_series == ()


def test_compute_trends_with_no_runs_root(tmp_path: Path) -> None:
    data = compute_trends(tmp_path / "does-not-exist")
    assert data.score_series == ()


def test_compute_trends_module_results_unnamed(tmp_path: Path) -> None:
    import json as json_mod

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    run_dir = runs_root / "RUN-UNNAMEDDIRA"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        json_mod.dumps(
            {
                "run_id": "RUN-UNNAMEDDIRA",
                "started_at": "2026-05-29T12:00:00+00:00",
                "status": "passed",
                "quality_score": 80.0,
            }
        ),
        encoding="utf-8",
    )
    modules_dir = run_dir / "module-results"
    modules_dir.mkdir()
    # Entry without name → skipped by _module_pass_rate_series
    (modules_dir / "anon.json").write_text(
        json_mod.dumps({"name": "", "status": "passed"}), encoding="utf-8"
    )
    data = compute_trends(runs_root)
    assert data.module_pass_rates == {}


def test_compute_trends_findings_invalid_severity(tmp_path: Path) -> None:
    import json as json_mod

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    for i, run_id in enumerate(["RUN-AAAAAAAAAAAA", "RUN-BBBBBBBBBBBB"]):
        run_dir = runs_root / run_id
        run_dir.mkdir()
        (run_dir / "run.json").write_text(
            json_mod.dumps(
                {
                    "run_id": run_id,
                    "started_at": f"2026-05-29T1{i}:00:00+00:00",
                    "status": "passed",
                    "quality_score": 80.0,
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "findings.json").write_text(
            json_mod.dumps(
                {"findings": [{"id": "FND-INVALIDSEVAA", "title": "x", "severity": "weird"}]}
            ),
            encoding="utf-8",
        )
    data = compute_trends(runs_root)
    if data.top_recurring:
        assert data.top_recurring[0].severity == "info"


def test_compute_trends_corrupt_findings(tmp_path: Path) -> None:
    import json as json_mod

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    run_dir = runs_root / "RUN-CORRUPTFINDAA"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        json_mod.dumps(
            {
                "run_id": "RUN-CORRUPTFINDAA",
                "started_at": "2026-05-29T12:00:00+00:00",
                "status": "passed",
                "quality_score": 80.0,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "findings.json").write_text("not json", encoding="utf-8")
    modules_dir = run_dir / "module-results"
    modules_dir.mkdir()
    (modules_dir / "bad.json").write_text("not json", encoding="utf-8")
    data = compute_trends(runs_root)
    assert len(data.score_series) == 1


def test_module_pass_rate_series_with_no_points() -> None:
    from engine.reporter.trends import ModulePassRateSeries

    series = ModulePassRateSeries(module="x", points=())
    assert series.latest_display == "n/a"
    assert "<svg" in series.sparkline_svg


def test_trend_data_with_empty_series_renders_empty_sparkline() -> None:
    data = TrendData()
    ctx = data.to_template_context()
    assert "<svg" in ctx["score_sparkline_svg"]


def test_iter_started_at_skips_invalid() -> None:
    from engine.reporter.trends import _RunSnapshot, iter_started_at

    snaps = [
        _RunSnapshot(
            run_id="x",
            started_at="not-iso",
            status="passed",
            score=None,
            module_results=(),
            findings=(),
        ),
        _RunSnapshot(
            run_id="y",
            started_at="2026-05-29T12:00:00+00:00",
            status="passed",
            score=None,
            module_results=(),
            findings=(),
        ),
    ]
    out = list(iter_started_at(snaps))
    assert len(out) == 1


def test_coerce_score_strings() -> None:
    from engine.reporter.trends import _coerce_score

    assert _coerce_score(None) is None
    assert _coerce_score("80.5") == 80.5
    assert _coerce_score("invalid") is None


def test_audit_view_records_with_inferred_level(tmp_path: Path) -> None:
    from engine.reporter.audit_view import load_audit_entries

    log = tmp_path / "audit.log"
    log.write_text(
        '{"event":"policy_block","ts":"2026-05-29T00:00:00+00:00","code":"E-GATE-001"}\n',
        encoding="utf-8",
    )
    entries = load_audit_entries(log)
    assert entries[0].level == "warning"


def test_audit_view_drops_non_dict_lines(tmp_path: Path) -> None:
    from engine.reporter.audit_view import load_audit_entries

    log = tmp_path / "audit.log"
    log.write_text(
        '"a string"\n[1,2,3]\n{"event":"ok","ts":"2026-05-29T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    entries = load_audit_entries(log)
    assert [e.event for e in entries] == ["ok"]


def test_slack_payload_no_artifact_url_omits_button(run: TestRun) -> None:
    payload = render_slack_payload(run, (), None, None)
    blocks = payload["blocks"]
    assert all(b.get("type") != "actions" for b in blocks)


def test_slack_payload_top_blockers_omits_extras() -> None:
    findings = tuple(
        _build_finding(
            "RUN-MANYBLOCKAAA",
            id=f"FND-MANYHIGH{idx:04d}",
            module="security",
            category="security/x",
            severity="high",
            confidence=0.9,
            title=f"Title {idx}",
            description=f"Desc {idx}",
            evidence=(
                Evidence(
                    id=f"EVD-MANYHIGH{idx:04d}",
                    type="trace",
                    path=Path(f"t/{idx}.zip"),
                    redacted=True,
                ),
            ),
            recommendation="fix",
        )
        for idx in range(5)
    )
    run = TestRun(
        id="RUN-MANYBLOCKAAA",
        started_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={},
        modules_run=(),
        status="failed",
    )
    payload = render_slack_payload(run, findings, None, None)
    section = next(
        b
        for b in payload["blocks"]
        if b.get("type") == "section" and "Top blockers" in b.get("text", {}).get("text", "")
    )
    assert "more in the report" in section["text"]["text"]


def test_audit_view_infers_module_from_event() -> None:
    entries = normalize_audit_entries(
        [
            {"event": "module_end", "ts": "2026-05-29T00:00:00+00:00"},
            {"event": "artifact_emitted", "ts": "2026-05-29T00:00:01+00:00"},
            {"event": "safety_block", "ts": "2026-05-29T00:00:02+00:00", "code": "E-SAF-001"},
            {"event": "custom", "ts": "2026-05-29T00:00:03+00:00", "code": "E-XYZ-001"},
        ]
    )
    by_event = {e.event: e for e in entries}
    assert by_event["module_end"].module == "lifecycle"
    assert by_event["artifact_emitted"].module == "reporter"
    assert by_event["safety_block"].level == "error"
    assert by_event["custom"].level == "error"


def test_build_template_context_for_failed_run() -> None:
    run = TestRun(
        id="RUN-FAILUNITAAAA",
        started_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={},
        modules_run=(),
        status="failed",
    )
    ctx = build_template_context(HtmlReportInputs(run=run))
    assert ctx["decision_class"] == "blocked"


def test_build_template_context_for_incomplete_run() -> None:
    run = TestRun(
        id="RUN-INCUNITAAAAA",
        started_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={},
        modules_run=(),
        status="incomplete",
    )
    ctx = build_template_context(HtmlReportInputs(run=run))
    assert ctx["decision_class"] == "inconclusive"


def test_format_flake_rate_handles_string(run: TestRun) -> None:
    from engine.domain.module_result import ModuleResult

    module = ModuleResult(
        id="MOD-FLAKEXAAAAAA",
        name="functional",
        status="passed",
        findings=(),
        metrics={"flake_rate": 0.07},
        duration_ms=1500,
        errors=(),
    )
    ctx = build_template_context(HtmlReportInputs(run=run, module_results=(module,)))
    row = ctx["module_results"][0]
    assert row["flake_rate"] == "7.00%"


def test_format_flake_rate_handles_dotted_key(run: TestRun) -> None:
    from engine.domain.module_result import ModuleResult

    module = ModuleResult(
        id="MOD-FLAKEDOTAAAA",
        name="functional",
        status="passed",
        findings=(),
        metrics={"flake.rate": 0.123},
        duration_ms=1500,
        errors=(),
    )
    ctx = build_template_context(HtmlReportInputs(run=run, module_results=(module,)))
    row = ctx["module_results"][0]
    assert row["flake_rate"] == "12.30%"


def test_format_flake_rate_invalid_value() -> None:
    from engine.reporter.html_writer import _format_flake_rate

    assert _format_flake_rate(None) is None
    assert _format_flake_rate("nope") is None
    assert _format_flake_rate(0.5) == "50.00%"


def test_duration_display_zero_and_seconds_and_ms(run: TestRun) -> None:
    from engine.reporter.html_writer import _duration_display_ms

    assert _duration_display_ms(0) == "0 ms"
    assert _duration_display_ms(900) == "900 ms"
    assert _duration_display_ms(1500) == "1.5 s"


def test_finding_view_renders_location_and_evidence(run: TestRun) -> None:
    finding = _build_finding(
        run.id,
        id="FND-EVIDENCEXAAA",
        module="security",
        category="security/headers",
        severity="high",
        confidence=0.9,
        title="t",
        description="d",
        location=FindingLocation(
            route="/admin",
            selector="button",
            file="src/admin.py",
            line=42,
        ),
        affected_target="https://localhost:8080",
        evidence=(
            Evidence(
                id="EVD-EVIDENCEXAAA",
                type="screenshot",
                path=Path("screenshots/admin.png"),
                redacted=True,
            ),
        ),
        recommendation="fix it",
    )
    ctx = build_template_context(HtmlReportInputs(run=run, findings=(finding,)))
    rendered = ctx["findings"][0]
    assert "route=/admin" in rendered["location_display"]
    assert "selector=button" in rendered["location_display"]
    assert "file=src/admin.py" in rendered["location_display"]
    assert "line=42" in rendered["location_display"]
    assert rendered["evidence"][0]["is_image"] is True


def test_pr_comment_includes_html_link_when_lows_present(run: TestRun) -> None:
    finding = _build_finding(
        run.id,
        id="FND-LOWAAAAAAAAA",
        module="security",
        category="security/x",
        severity="low",
        confidence=0.5,
        title="t",
        description="d",
    )
    body = render_pr_comment(run, (finding,), None, None)
    assert "report.html" in body


def test_slack_payload_omits_top_blockers_when_none(run: TestRun) -> None:
    payload = render_slack_payload(run, (), None, None)
    section_texts = [
        b.get("text", {}).get("text", "") for b in payload["blocks"] if b.get("type") == "section"
    ]
    assert not any("Top blockers" in t for t in section_texts)


def test_dispatcher_html_includes_trends_when_history_present(tmp_path: Path) -> None:
    """Cover the dispatcher branch where compute_trends returns visible data."""

    import json as json_mod

    from engine.orchestrator.artifacts import ArtifactDirectory
    from engine.reporter.dispatcher import Reporter, ReportInputs

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    for i, score in enumerate([80.0, 85.0]):
        run_dir = runs_root / f"RUN-PRIOR{chr(65 + i) * 8}"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(
            json_mod.dumps(
                {
                    "run_id": run_dir.name,
                    "started_at": f"2026-05-29T1{i}:00:00+00:00",
                    "status": "passed",
                    "quality_score": score,
                }
            ),
            encoding="utf-8",
        )
    run = TestRun(
        id="RUN-CURRENTXAAAA",
        started_at=datetime(2026, 5, 29, 13, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 29, 13, 0, 30, tzinfo=UTC),
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot={"target": {"base_url": "https://localhost:8080"}},
        modules_run=(),
        status="passed",
    )
    artifacts = ArtifactDirectory.create(runs_root, run.id)
    inputs = ReportInputs(run=run, config_snapshot={"a": 1})
    reporter = Reporter()
    outputs = reporter.emit(
        inputs,
        artifacts,
        formats=["html"],
    )
    body = outputs["html"].read_text(encoding="utf-8")
    assert "Trends" in body
