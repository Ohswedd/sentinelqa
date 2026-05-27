"""SARIF 2.1.0 emitter (task 03.05).

Serializes SentinelQA findings as a SARIF 2.1.0 log so GitHub
code-scanning and other SARIF-aware security tools can ingest results
without custom parsing. Schema: ``packages/shared-schema/external/
sarif-2.1.0.json`` (vendored copy of the official OASIS schema).

Severity → SARIF ``level`` mapping (per task spec):

- ``critical`` / ``high`` → ``error``
- ``medium`` → ``warning``
- ``low`` / ``info`` → ``note``

Each unique category produces one ``reportingDescriptor`` in
``tool.driver.rules``. The writer asks
:class:`engine.reporter.sarif_rules.SarifRuleRegistry` for the rule
attached to a category; unregistered categories fall back to a
synthesized placeholder so the SARIF document is always schema-valid
even before Phase 13+ registers concrete rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlparse

from engine.domain.finding import Finding, Severity
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.sarif_rules import SarifRule, SarifRuleRegistry, default_sarif_registry

SARIF_VERSION: Final[str] = "2.1.0"
SARIF_SCHEMA_URI: Final[str] = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
)
TOOL_NAME: Final[str] = "SentinelQA"
TOOL_VERSION: Final[str] = "0.0.0"
TOOL_INFORMATION_URI: Final[str] = "https://sentinelqa.dev"

SEVERITY_TO_LEVEL: Final[dict[Severity, str]] = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}


def write_sarif(
    artifact_dir: ArtifactDirectory,
    findings: Sequence[Finding],
    run: TestRun,
    *,
    registry: SarifRuleRegistry | None = None,
    filename: str = "sarif.json",
) -> Path:
    """Persist a SARIF 2.1.0 log of ``findings``. Returns the written path."""

    document = build_sarif_document(findings, run, registry=registry)
    # SARIF nests results/locations/rules deeply; the default 6-deep
    # redaction limit would mask whole subtrees. Bump to 12 — still
    # capped so adversarial inputs can't drive runaway recursion.
    return artifact_dir.write_json(filename, document, redaction_depth=12)


def build_sarif_document(
    findings: Sequence[Finding],
    run: TestRun,
    *,
    registry: SarifRuleRegistry | None = None,
) -> dict[str, Any]:
    """Build the SARIF document (pure function; useful for tests)."""

    reg = registry or default_sarif_registry()

    # Deduplicate rules in stable order (sorted by category) so the
    # rules array is reproducible across runs.
    categories: list[str] = []
    seen: set[str] = set()
    for f in findings:
        if f.category not in seen:
            seen.add(f.category)
            categories.append(f.category)
    categories.sort()
    rules: list[SarifRule] = [reg.get(c) for c in categories]
    category_to_index: dict[str, int] = {r.category: i for i, r in enumerate(rules)}

    results: list[dict[str, Any]] = []
    for f in findings:
        rule = reg.get(f.category)
        results.append(_finding_to_result(f, rule, category_to_index[f.category], run))

    document: dict[str, Any] = {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                        "informationUri": TOOL_INFORMATION_URI,
                        "rules": [r.to_descriptor() for r in rules],
                    }
                },
                "automationDetails": {"id": run.id},
                "results": results,
            }
        ],
    }
    return document


def _finding_to_result(
    finding: Finding,
    rule: SarifRule,
    rule_index: int,
    run: TestRun,
) -> dict[str, Any]:
    level = SEVERITY_TO_LEVEL.get(finding.severity, "warning")
    message_text = finding.title.strip()
    description = finding.description.strip()
    if description:
        message_text = f"{message_text}\n\n{description}"

    result: dict[str, Any] = {
        "ruleId": rule.id,
        "ruleIndex": rule_index,
        "level": level,
        "message": {"text": message_text},
        "locations": [_finding_to_location(finding, run)],
        "properties": {
            "confidence": round(float(finding.confidence), 4),
            "severity": finding.severity,
            "category": finding.category,
            "module": finding.module,
            "finding_id": finding.id,
        },
    }
    if finding.evidence:
        result["properties"]["evidence"] = [
            {"type": e.type, "path": str(e.path), "id": e.id} for e in finding.evidence
        ]
    return result


def _finding_to_location(finding: Finding, run: TestRun) -> dict[str, Any]:
    """Build the SARIF ``location`` object from a Finding."""

    uri = _location_uri(finding, run)
    artifact: dict[str, Any] = {"uri": uri}
    physical: dict[str, Any] = {"artifactLocation": artifact}

    if finding.location.line is not None:
        physical["region"] = {"startLine": max(1, finding.location.line or 1)}

    location: dict[str, Any] = {"physicalLocation": physical}
    if finding.location.selector:
        location["logicalLocations"] = [{"name": finding.location.selector, "kind": "element"}]
    return location


def _location_uri(finding: Finding, run: TestRun) -> str:
    """Derive the SARIF artifact URI from a Finding.

    Preference order:

    1. ``finding.location.file`` — a workspace-relative source ref.
    2. ``finding.location.route`` — joined onto the run's ``base_url``.
    3. The run's ``base_url`` host as a last resort so the URI is never
       empty (the SARIF schema requires a non-empty uri).
    """

    if finding.location.file:
        return finding.location.file
    if finding.location.route:
        base = str(run.target.base_url).rstrip("/")
        route = finding.location.route
        if not route.startswith("/"):
            route = "/" + route
        return base + route
    parsed = urlparse(str(run.target.base_url))
    return f"{parsed.scheme}://{parsed.hostname or 'localhost'}/"


__all__ = [
    "SARIF_SCHEMA_URI",
    "SARIF_VERSION",
    "SEVERITY_TO_LEVEL",
    "TOOL_INFORMATION_URI",
    "TOOL_NAME",
    "TOOL_VERSION",
    "build_sarif_document",
    "write_sarif",
]
