"""Golden tests for the JUnit XML emitter."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.junit_writer import render_junit_xml, write_junit

from tests.conftest import assert_matches_golden


def test_junit_golden_passing(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_junit(
        artifacts,
        fixture_test_run_passed,
        module_results=fixture_module_results_passing,
        findings=fixture_findings_mixed,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "junit" / "junit.passing.golden.xml")


def test_junit_golden_failed(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_module_results_blocked: tuple[ModuleResult, ...],
    fixture_findings_critical: tuple[Finding, ...],
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_junit(
        artifacts,
        fixture_test_run_passed,
        module_results=fixture_module_results_blocked,
        findings=fixture_findings_critical,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "junit" / "junit.failed.golden.xml")


def test_junit_golden_empty(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_junit(artifacts, fixture_test_run_passed)
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "junit" / "junit.empty.golden.xml")


def test_junit_render_is_parseable_xml(
    fixture_test_run_passed: TestRun,
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    xml = render_junit_xml(
        fixture_test_run_passed,
        module_results=fixture_module_results_passing,
        findings=fixture_findings_mixed,
    )
    # Will raise on malformed XML.
    root = ET.fromstring(xml)
    assert root.tag == "testsuites"
    assert root.get("name", "").startswith("sentinelqa-RUN-")


def test_junit_failure_promoted_for_critical_and_high(
    fixture_test_run_passed: TestRun,
    fixture_findings_critical: tuple[Finding, ...],
) -> None:
    xml = render_junit_xml(
        fixture_test_run_passed,
        findings=fixture_findings_critical,
    )
    root = ET.fromstring(xml)
    failures = root.findall(".//failure")
    assert len(failures) == 1
    fail = failures[0]
    assert fail.get("type") == "critical"


def test_junit_skipped_module_emits_skipped_element(
    fixture_test_run_passed: TestRun,
    fixture_module_results_blocked: tuple[ModuleResult, ...],
) -> None:
    xml = render_junit_xml(
        fixture_test_run_passed,
        module_results=fixture_module_results_blocked,
    )
    root = ET.fromstring(xml)
    skipped = root.findall(".//skipped")
    assert len(skipped) >= 1


def test_junit_errored_module_emits_error_element(
    fixture_test_run_passed: TestRun,
    fixture_module_results_blocked: tuple[ModuleResult, ...],
) -> None:
    xml = render_junit_xml(
        fixture_test_run_passed,
        module_results=fixture_module_results_blocked,
    )
    root = ET.fromstring(xml)
    errors = root.findall(".//error")
    assert len(errors) >= 1


def test_junit_redacts_authorization_header(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_module_results_passing: tuple[ModuleResult, ...],
) -> None:
    written = write_junit(
        tmp_path_artifacts := ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id),
        fixture_test_run_passed,
        module_results=fixture_module_results_passing,
        system_out="Bearer sk-leaked-secret-token-here",
    )
    assert tmp_path_artifacts.root.exists()
    body = written.read_text(encoding="utf-8")
    assert "sk-leaked-secret-token-here" not in body
    assert "REDACTED" in body
