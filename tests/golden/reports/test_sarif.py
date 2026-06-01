"""Golden tests for the SARIF 2.1.0 emitter."""

from __future__ import annotations

import json
from pathlib import Path

from engine.domain.finding import Finding
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.sarif_rules import SarifRule, SarifRuleRegistry
from engine.reporter.sarif_writer import (
    SARIF_VERSION,
    SEVERITY_TO_LEVEL,
    build_sarif_document,
    write_sarif,
)

from tests.conftest import assert_matches_golden


def _registry() -> SarifRuleRegistry:
    """A fresh registry with the rules every golden expects."""
    reg = SarifRuleRegistry()
    reg.register(
        SarifRule(
            id="SEC-001",
            name="MissingSecureFlag",
            short_description="Session cookie missing Secure flag.",
            full_description=(
                "The Set-Cookie response header lacks Secure; the cookie may be "
                "transmitted over an unencrypted channel."
            ),
            help_uri="https://docs.sentinelqa.dev/rules/SEC-001",
            category="security/headers",
            default_severity="error",
        )
    )
    reg.register(
        SarifRule(
            id="SEC-002",
            name="MissingHttpOnly",
            short_description="Session cookie missing HttpOnly attribute.",
            full_description="The Set-Cookie response header lacks HttpOnly.",
            help_uri="https://docs.sentinelqa.dev/rules/SEC-002",
            category="security/cookies",
            default_severity="error",
        )
    )
    reg.register(
        SarifRule(
            id="A11Y-001",
            name="InsufficientContrast",
            short_description="Foreground/background contrast below WCAG AA threshold.",
            full_description="Contrast ratio < 4.5 fails WCAG 2.1 AA for normal text.",
            help_uri="https://docs.sentinelqa.dev/rules/A11Y-001",
            category="a11y/contrast",
            default_severity="warning",
        )
    )
    reg.register(
        SarifRule(
            id="PERF-001",
            name="LcpWithinBudget",
            short_description="Largest Contentful Paint within configured budget.",
            full_description="LCP measured under the 2.5s default budget.",
            help_uri="https://docs.sentinelqa.dev/rules/PERF-001",
            category="perf/lcp",
            default_severity="note",
        )
    )
    return reg


def test_sarif_golden_empty(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_sarif(artifacts, (), fixture_test_run_passed, registry=_registry())
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "sarif" / "sarif.empty.golden.json")


def test_sarif_golden_critical(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_critical: tuple[Finding, ...],
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_sarif(
        artifacts,
        fixture_findings_critical,
        fixture_test_run_passed,
        registry=_registry(),
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "sarif" / "sarif.critical.golden.json")


def test_sarif_golden_mixed(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_sarif(
        artifacts,
        fixture_findings_mixed,
        fixture_test_run_passed,
        registry=_registry(),
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "sarif" / "sarif.mixed.golden.json")


def test_sarif_document_pinned_to_2_1_0(
    fixture_test_run_passed: TestRun,
) -> None:
    doc = build_sarif_document((), fixture_test_run_passed, registry=_registry())
    assert doc["version"] == SARIF_VERSION


def test_sarif_severity_to_level_mapping(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    doc = build_sarif_document(
        fixture_findings_mixed, fixture_test_run_passed, registry=_registry()
    )
    levels_by_severity: dict[str, str] = {}
    for finding, result in zip(fixture_findings_mixed, doc["runs"][0]["results"], strict=True):
        levels_by_severity[finding.severity] = result["level"]
    for severity, level in levels_by_severity.items():
        assert level == SEVERITY_TO_LEVEL[severity]  # type: ignore[index]


def test_sarif_unregistered_category_synthesizes_rule(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_critical: tuple[Finding, ...],
) -> None:
    # Use the default (empty) registry; rule should be synthesized.
    empty_registry = SarifRuleRegistry()
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_sarif(
        artifacts,
        fixture_findings_critical,
        fixture_test_run_passed,
        registry=empty_registry,
    )
    doc = json.loads(written.read_text(encoding="utf-8"))
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 1
    assert rules[0]["id"].startswith("GEN-")
    assert doc["runs"][0]["results"][0]["ruleId"] == rules[0]["id"]


def test_sarif_redacts_authorization_header_in_description(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_finished_at: object,
) -> None:
    from datetime import datetime

    from engine.domain.finding import FindingLocation

    assert isinstance(fixture_finished_at, datetime)

    finding = Finding(
        id="FND-LEAKAAAAAAAA",
        run_id=fixture_test_run_passed.id,
        module="security",
        category="security/headers",
        severity="critical",
        confidence=0.95,
        title="Secret token logged in error body",
        description=(
            "GET /api/secret returned 500 with header Authorization: Bearer "
            "sk-this-should-never-be-emitted-token in the response body."
        ),
        location=FindingLocation(route="/api/secret"),
        evidence=(),
        recommendation="Strip Authorization from error responses.",
        affected_target="https://localhost:8080",
        created_at=fixture_finished_at,
    )
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_sarif(artifacts, (finding,), fixture_test_run_passed, registry=_registry())
    body = written.read_text(encoding="utf-8")
    assert "sk-this-should-never-be-emitted-token" not in body
    assert "REDACTED" in body


def test_sarif_rules_sorted_by_category(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    doc = build_sarif_document(
        fixture_findings_mixed, fixture_test_run_passed, registry=_registry()
    )
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    categories = [r["properties"]["category"] for r in rules]
    assert categories == sorted(categories)
