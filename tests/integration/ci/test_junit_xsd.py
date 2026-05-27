"""XSD validation for emitted JUnit XML (task 03.04).

Runs the SentinelQA JUnit writer through every Phase-03 fixture and
validates the bytes against the committed XSD at
``packages/shared-schema/external/junit.xsd``. Skips if ``lxml`` is not
importable (the XSD validator stays optional so the basic test suite
runs on minimal environments).
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lxml import etree as lxml_etree
except ImportError:  # pragma: no cover - covered by env-specific CI
    lxml_etree = None  # type: ignore[assignment]

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.test_run import TestRun
from engine.reporter.junit_writer import render_junit_xml

REPO_ROOT = Path(__file__).resolve().parents[3]
XSD_PATH = REPO_ROOT / "packages" / "shared-schema" / "external" / "junit.xsd"


def _validate(xml: str) -> None:
    if lxml_etree is None:
        pytest.skip("lxml not installed")
    schema_doc = lxml_etree.parse(str(XSD_PATH))
    schema = lxml_etree.XMLSchema(schema_doc)
    parser = lxml_etree.XMLParser(resolve_entities=False, no_network=True)
    doc = lxml_etree.fromstring(xml.encode("utf-8"), parser=parser)
    schema.assertValid(doc)


def test_junit_passing_run_validates_against_xsd(
    fixture_test_run_passed: TestRun,
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    xml = render_junit_xml(
        fixture_test_run_passed,
        module_results=fixture_module_results_passing,
        findings=fixture_findings_mixed,
    )
    _validate(xml)


def test_junit_failed_run_validates_against_xsd(
    fixture_test_run_passed: TestRun,
    fixture_module_results_blocked: tuple[ModuleResult, ...],
    fixture_findings_critical: tuple[Finding, ...],
) -> None:
    xml = render_junit_xml(
        fixture_test_run_passed,
        module_results=fixture_module_results_blocked,
        findings=fixture_findings_critical,
    )
    _validate(xml)


def test_junit_empty_run_validates_against_xsd(
    fixture_test_run_passed: TestRun,
) -> None:
    xml = render_junit_xml(fixture_test_run_passed)
    _validate(xml)
