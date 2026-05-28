"""Integration tests — SARIF output carries every triggered security rule.

Phase 13.10. We synthesize a small SARIF payload via the Phase-03 writer
using a curated set of findings whose categories match registered
security rules, then assert the resulting SARIF document includes those
rules in ``runs[0].tool.driver.rules``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.ids import IdGenerator
from engine.domain.test_run import TestRun
from engine.reporter.sarif_rules import default_sarif_registry
from engine.reporter.sarif_writer import build_sarif_document

import modules.security  # noqa: F401 — register security rules


def _finding(
    rule_id: str,
    category: str,
    *,
    id_gen: IdGenerator,
    severity: str = "high",
) -> Finding:
    return Finding(
        id=id_gen.new("FND"),
        run_id="RUN-AAAAAAAAAAAA",
        module="security",
        category=category,
        severity=severity,  # type: ignore[arg-type]
        confidence=0.9,
        title=f"Finding for {rule_id}",
        description=f"Synthetic finding for SARIF rule {rule_id}",
        location=FindingLocation(route="/login"),
        evidence=(
            Evidence(id=id_gen.new("EVD"), type="api_sample", path=Path("security/headers.json")),
        ),
        created_at=datetime.now(UTC),
    )


def _test_run(id_gen: IdGenerator) -> TestRun:
    from engine.domain.target import Target

    target = Target(base_url="http://localhost/", allowed_hosts=frozenset({"localhost"}))
    started = datetime.now(UTC)
    return TestRun(
        id=id_gen.new("RUN"),
        started_at=started,
        finished_at=started,
        target=target,
        config_snapshot={},
        modules_run=("security",),
        status="passed",
    )


def test_sarif_contains_registered_security_rules() -> None:
    id_gen = IdGenerator()
    findings = (
        _finding(
            "SEC-HEADERS-HSTS-MISSING",
            "security/headers/hsts_missing",
            id_gen=id_gen,
        ),
        _finding(
            "SEC-COOKIE-MISSING-SECURE",
            "security/cookies/missing_secure",
            id_gen=id_gen,
        ),
        _finding(
            "SEC-DEPS-VULNERABLE",
            "security/deps/vulnerable",
            id_gen=id_gen,
            severity="critical",
        ),
    )
    payload = build_sarif_document(findings, _test_run(id_gen), registry=default_sarif_registry())
    rules = payload["runs"][0]["tool"]["driver"]["rules"]
    rule_ids = {r["id"] for r in rules}
    assert "SEC-HEADERS-HSTS-MISSING" in rule_ids
    assert "SEC-COOKIE-MISSING-SECURE" in rule_ids
    assert "SEC-DEPS-VULNERABLE" in rule_ids


def test_sarif_schema_valid_with_security_findings() -> None:
    id_gen = IdGenerator()
    findings = (
        _finding(
            "SEC-XSS-REFLECTED",
            "security/xss/reflected",
            id_gen=id_gen,
        ),
    )
    payload = build_sarif_document(findings, _test_run(id_gen), registry=default_sarif_registry())
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "shared-schema"
        / "external"
        / "sarif-2.1.0.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)
