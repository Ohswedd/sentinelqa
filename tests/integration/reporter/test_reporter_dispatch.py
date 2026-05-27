"""Reporter dispatcher integration tests (task 03.07).

Verifies that:

- A passing run with rich data emits every requested format and writes
  one audit-log entry per artifact.
- Disabling a format in config skips its writer (and its audit entry).
- A run with no findings still emits run.json + score.json + markdown
  (no findings.json — empty findings produce no file).
- Format aliases (`json` → run+findings+score, `html` → no-op) work.
- The dispatcher returns a deterministic Path map keyed by format name.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.audit_log import read_audit_log
from engine.reporter.dispatcher import (
    SUPPORTED_FORMATS,
    Reporter,
    ReportInputs,
)


def _inputs(
    run: TestRun,
    *,
    findings: tuple[Finding, ...] = (),
    module_results: tuple[ModuleResult, ...] = (),
    score: QualityScore | None = None,
    policy: PolicyDecision | None = None,
) -> ReportInputs:
    return ReportInputs(
        run=run,
        findings=findings,
        module_results=module_results,
        score=score,
        policy=policy,
        config_snapshot=run.config_snapshot,
    )


def test_emit_passing_run_writes_every_requested_format(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    audit_log = artifacts.path("audit.log")
    reporter = Reporter()
    outputs = reporter.emit(
        _inputs(
            fixture_test_run_passed,
            findings=fixture_findings_mixed,
            module_results=fixture_module_results_passing,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
        ),
        artifacts,
        formats=SUPPORTED_FORMATS,
        audit_log_path=audit_log,
    )
    expected = {"run", "findings", "score", "junit", "sarif", "markdown"}
    assert set(outputs.keys()) == expected
    for fmt, path in outputs.items():
        assert path.exists(), f"{fmt} writer produced no file"
        assert path.parent == artifacts.root


def test_emit_audit_log_records_one_entry_per_artifact(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    audit_log = artifacts.path("audit.log")
    reporter = Reporter()
    outputs = reporter.emit(
        _inputs(
            fixture_test_run_passed,
            findings=fixture_findings_mixed,
            module_results=fixture_module_results_passing,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
        ),
        artifacts,
        formats=SUPPORTED_FORMATS,
        audit_log_path=audit_log,
    )
    entries = read_audit_log(audit_log)
    artifact_events = [e for e in entries if e.get("event") == "artifact_emitted"]
    formats_logged = {e["format"] for e in artifact_events}
    assert formats_logged == set(outputs.keys())


def test_emit_disabled_format_is_skipped(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    reporter = Reporter()
    outputs = reporter.emit(
        _inputs(
            fixture_test_run_passed,
            findings=fixture_findings_mixed,
            module_results=fixture_module_results_passing,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
        ),
        artifacts,
        formats=["run", "markdown"],  # explicitly minimal
    )
    assert set(outputs.keys()) == {"run", "markdown"}
    # Files NOT requested do not exist.
    assert not artifacts.path("findings.json").exists()
    assert not artifacts.path("junit.xml").exists()
    assert not artifacts.path("sarif.json").exists()


def test_emit_json_alias_expands_to_trio(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    reporter = Reporter()
    outputs = reporter.emit(
        _inputs(
            fixture_test_run_passed,
            findings=fixture_findings_mixed,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
        ),
        artifacts,
        formats=["json"],
    )
    # html alias expands to nothing in Phase 03 (placeholder).
    assert set(outputs.keys()) == {"run", "findings", "score"}


def test_emit_html_alias_currently_only_writes_run(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
) -> None:
    """`html` is a Phase-15 placeholder. Requesting only `html` still
    produces `run.json` because it's the canonical lifecycle artifact."""
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    reporter = Reporter()
    outputs = reporter.emit(
        _inputs(fixture_test_run_passed),
        artifacts,
        formats=["html"],
    )
    assert set(outputs.keys()) == {"run"}


def test_emit_skips_findings_when_no_findings(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    reporter = Reporter()
    outputs = reporter.emit(
        _inputs(
            fixture_test_run_passed,
            findings=(),
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
        ),
        artifacts,
        formats=["json", "markdown"],
    )
    # findings.json should NOT be written when there are no findings.
    assert "findings" not in outputs
    assert {"run", "score", "markdown"} <= set(outputs.keys())


def test_run_json_artifact_paths_match_requested_formats(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    reporter = Reporter()
    outputs = reporter.emit(
        _inputs(
            fixture_test_run_passed,
            findings=fixture_findings_mixed,
            module_results=fixture_module_results_passing,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
        ),
        artifacts,
        formats=["run", "findings", "score", "junit", "markdown"],
    )
    payload = json.loads(outputs["run"].read_text(encoding="utf-8"))
    paths = payload["artifact_paths"]
    assert paths["findings"] == "findings.json"
    assert paths["score"] == "score.json"
    assert paths["junit"] == "junit.xml"
    assert paths["report_md"] == "report.md"
    # SARIF was not requested → null.
    assert paths["sarif"] is None
    # HTML not in Phase 03.
    assert paths["report_html"] is None
