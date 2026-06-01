"""SARIF 2.1.0 emitter.

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
even before + registers concrete rules.
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

# Taxonomy descriptors emitted under ``tool.driver.taxa`` when any finding
# carries a CWE / ATT&CK / OWASP-API id (, ADR-0044). SARIF 2.1.0
# §3.19 ``toolComponent.taxa`` is the canonical way to attach standards
# references to results.
_TAXA_CWE_NAME: Final[str] = "CWE"
_TAXA_CWE_URI: Final[str] = "https://cwe.mitre.org"
_TAXA_ATTACK_NAME: Final[str] = "MITRE-ATTACK"
_TAXA_ATTACK_URI: Final[str] = "https://attack.mitre.org"
_TAXA_OWASP_API_NAME: Final[str] = "OWASP-API-Top10-2023"
_TAXA_OWASP_API_URI: Final[str] = "https://owasp.org/API-Security/editions/2023/en/0x11-t10/"


def _cwe_help_uri(cwe_id: str) -> str:
    number = cwe_id.removeprefix("CWE-")
    return f"https://cwe.mitre.org/data/definitions/{number}.html"


def _attack_help_uri(attack_id: str) -> str:
    base, _, sub = attack_id.partition(".")
    if sub:
        return f"https://attack.mitre.org/techniques/{base}/{sub}/"
    return f"https://attack.mitre.org/techniques/{base}/"


def _owasp_api_help_uri(owasp_api_id: str) -> str:
    # ``API-2023-01`` → ``xa1-broken-object-level-authorization``
    # We don't know the slug; surface the editions index instead.
    return _TAXA_OWASP_API_URI


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

    # Collect every distinct taxonomy id referenced by any finding so we
    # can emit a deterministic ``tool.driver.taxa`` array and point each
    # result at it via ``taxa`` references (SARIF 2.1.0 §3.19).
    cwe_ids: list[str] = sorted({f.cwe_id for f in findings if f.cwe_id})
    attack_ids: list[str] = sorted({f.attack_id for f in findings if f.attack_id})
    owasp_api_ids: list[str] = sorted({f.owasp_api_id for f in findings if f.owasp_api_id})

    cwe_index = {ident: i for i, ident in enumerate(cwe_ids)}
    attack_index = {ident: i for i, ident in enumerate(attack_ids)}
    owasp_index = {ident: i for i, ident in enumerate(owasp_api_ids)}

    results: list[dict[str, Any]] = []
    for f in findings:
        rule = reg.get(f.category)
        results.append(
            _finding_to_result(
                f,
                rule,
                category_to_index[f.category],
                run,
                cwe_index=cwe_index,
                attack_index=attack_index,
                owasp_index=owasp_index,
            )
        )

    taxonomies = _build_taxonomies(cwe_ids, attack_ids, owasp_api_ids)

    driver: dict[str, Any] = {
        "name": TOOL_NAME,
        "version": TOOL_VERSION,
        "informationUri": TOOL_INFORMATION_URI,
        "rules": [r.to_descriptor() for r in rules],
    }
    if taxonomies:
        driver["supportedTaxonomies"] = [{"name": t["name"]} for t in taxonomies if t["taxa"]]

    sarif_run: dict[str, Any] = {
        "tool": {"driver": driver},
        "automationDetails": {"id": run.id},
        "results": results,
    }
    if taxonomies:
        sarif_run["taxonomies"] = taxonomies

    document: dict[str, Any] = {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [sarif_run],
    }
    return document


def _build_taxonomies(
    cwe_ids: list[str],
    attack_ids: list[str],
    owasp_api_ids: list[str],
) -> list[dict[str, Any]]:
    """Build the SARIF ``runs[].taxonomies`` array. Empty arrays are kept
    so the result references the correct, stable taxonomy indices.
    """

    if not (cwe_ids or attack_ids or owasp_api_ids):
        return []
    return [
        {
            "name": _TAXA_CWE_NAME,
            "informationUri": _TAXA_CWE_URI,
            "shortDescription": {"text": "Common Weakness Enumeration"},
            "taxa": [
                {
                    "id": cid,
                    "name": cid,
                    "shortDescription": {"text": cid},
                    "helpUri": _cwe_help_uri(cid),
                }
                for cid in cwe_ids
            ],
        },
        {
            "name": _TAXA_ATTACK_NAME,
            "informationUri": _TAXA_ATTACK_URI,
            "shortDescription": {"text": "MITRE ATT&CK technique catalog"},
            "taxa": [
                {
                    "id": aid,
                    "name": aid,
                    "shortDescription": {"text": aid},
                    "helpUri": _attack_help_uri(aid),
                }
                for aid in attack_ids
            ],
        },
        {
            "name": _TAXA_OWASP_API_NAME,
            "informationUri": _TAXA_OWASP_API_URI,
            "shortDescription": {"text": "OWASP API Security Top-10 (2023)"},
            "taxa": [
                {
                    "id": oid,
                    "name": oid,
                    "shortDescription": {"text": oid},
                    "helpUri": _owasp_api_help_uri(oid),
                }
                for oid in owasp_api_ids
            ],
        },
    ]


def _finding_to_result(
    finding: Finding,
    rule: SarifRule,
    rule_index: int,
    run: TestRun,
    *,
    cwe_index: dict[str, int] | None = None,
    attack_index: dict[str, int] | None = None,
    owasp_index: dict[str, int] | None = None,
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
    taxa_refs = _taxa_references(
        finding,
        cwe_index=cwe_index,
        attack_index=attack_index,
        owasp_index=owasp_index,
    )
    if taxa_refs:
        result["taxa"] = taxa_refs
    if finding.cwe_id:
        result["properties"]["cwe_id"] = finding.cwe_id
    if finding.attack_id:
        result["properties"]["attack_id"] = finding.attack_id
    if finding.owasp_api_id:
        result["properties"]["owasp_api_id"] = finding.owasp_api_id
    return result


def _taxa_references(
    finding: Finding,
    *,
    cwe_index: dict[str, int] | None,
    attack_index: dict[str, int] | None,
    owasp_index: dict[str, int] | None,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if finding.cwe_id and cwe_index and finding.cwe_id in cwe_index:
        refs.append(
            {
                "id": finding.cwe_id,
                "index": cwe_index[finding.cwe_id],
                "toolComponent": {"name": _TAXA_CWE_NAME},
            }
        )
    if finding.attack_id and attack_index and finding.attack_id in attack_index:
        refs.append(
            {
                "id": finding.attack_id,
                "index": attack_index[finding.attack_id],
                "toolComponent": {"name": _TAXA_ATTACK_NAME},
            }
        )
    if finding.owasp_api_id and owasp_index and finding.owasp_api_id in owasp_index:
        refs.append(
            {
                "id": finding.owasp_api_id,
                "index": owasp_index[finding.owasp_api_id],
                "toolComponent": {"name": _TAXA_OWASP_API_NAME},
            }
        )
    return refs


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
