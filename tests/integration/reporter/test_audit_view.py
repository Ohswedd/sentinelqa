"""Audit trail view."""

from __future__ import annotations

import json
from pathlib import Path

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.audit_log import write_audit_entry
from engine.reporter.audit_view import (
    load_audit_entries,
    normalize_audit_entries,
)
from engine.reporter.html_writer import HtmlReportInputs, render_html_report


def test_load_audit_entries_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_audit_entries(tmp_path / "nope.log") == ()


def test_load_audit_entries_normalizes_records(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    write_audit_entry(log, {"event": "safety_block", "code": "E-SAF-001", "message": "Public host"})
    write_audit_entry(log, {"event": "artifact_emitted", "format": "run", "path": "run.json"})
    entries = load_audit_entries(log)
    assert len(entries) == 2
    safety, artifact = entries
    assert safety.event == "safety_block"
    assert safety.level == "error"
    assert safety.module == "policy"
    assert "code=E-SAF-001" in safety.detail
    assert artifact.event == "artifact_emitted"
    assert artifact.module == "reporter"
    assert "format=run" in artifact.detail


def test_load_audit_entries_drops_malformed_lines(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    log.write_text(
        '{"event":"ok","ts":"2026-05-29T00:00:00+00:00"}\n'
        "this is not json\n"
        '{"event":"also_ok","ts":"2026-05-29T00:00:01+00:00"}\n',
        encoding="utf-8",
    )
    entries = load_audit_entries(log)
    assert [e.event for e in entries] == ["ok", "also_ok"]


def test_normalize_audit_entries_inline() -> None:
    entries = normalize_audit_entries(
        [
            {
                "event": "module_start",
                "ts": "2026-05-29T00:00:00+00:00",
                "module": "functional",
            }
        ]
    )
    assert entries[0].module == "functional"
    assert entries[0].level == "info"


def test_audit_view_does_not_leak_secrets(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    write_audit_entry(
        log,
        {
            "event": "request",
            "url": "https://example.com",
            "authorization": "Bearer sk_live_VERYSECRET",
            "password": "hunter2",
        },
    )
    raw_log = log.read_text(encoding="utf-8")
    # The audit writer itself runs redaction; downstream view never
    # un-redacts. Both the source and the loaded entry must show the
    # redaction marker.
    assert "VERYSECRET" not in raw_log
    assert "hunter2" not in raw_log
    entries = load_audit_entries(log)
    serialized = json.dumps([e.raw for e in entries])
    assert "VERYSECRET" not in serialized
    assert "hunter2" not in serialized


def test_html_report_embeds_audit_entries(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    log = artifacts.path("audit.log")
    write_audit_entry(log, {"event": "module_start", "module": "functional"})
    write_audit_entry(
        log,
        {
            "event": "policy_block",
            "decision": "blocked",
            "code": "E-GATE-001",
            "message": "Critical finding present",
        },
    )
    audit_entries = load_audit_entries(log)
    body = render_html_report(
        HtmlReportInputs(
            run=fixture_test_run_passed,
            findings=fixture_findings_mixed,
            module_results=fixture_module_results_passing,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
            audit_entries=audit_entries,
        )
    )
    assert "Audit trail" in body
    assert "module_start" in body
    assert "policy_block" in body
    assert "E-GATE-001" in body
    # Filter controls render
    assert 'data-filter="audit-level"' in body
    assert 'data-filter="audit-module"' in body


def test_audit_view_handles_no_entries(
    fixture_test_run_passed: TestRun,
) -> None:
    body = render_html_report(HtmlReportInputs(run=fixture_test_run_passed))
    assert "No audit log entries" in body
