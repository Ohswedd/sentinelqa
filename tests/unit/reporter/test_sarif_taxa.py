"""SARIF taxa emission tests ( / ADR-0044)."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.finding import Finding, FindingLocation
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.reporter.sarif_writer import build_sarif_document

GEN = IdGenerator()


def _finding(**overrides) -> Finding:
    kwargs = {
        "id": GEN.new("FND"),
        "run_id": GEN.new("RUN"),
        "module": "security",
        "category": "security/jwt_weakness/sec-jwt-alg-none",
        "severity": "critical",
        "confidence": 0.99,
        "title": "JWT alg=none accepted",
        "description": "Server accepted alg=none.",
        "location": FindingLocation(route="/api/me"),
        "evidence": (),
        "suggested_fix": None,
        "affected_target": "http://localhost:3000",
        "recommendation": "Reject alg=none at the verifier.",
        "created_at": datetime.now(UTC),
        "cwe_id": "CWE-347",
        "attack_id": "T1606.001",
        "owasp_api_id": "API-2023-08",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)


def _run() -> TestRun:
    return TestRun(
        id=GEN.new("RUN"),
        started_at=datetime.now(UTC),
        target=Target(
            base_url="http://localhost:3000",
            allowed_hosts=frozenset({"localhost"}),
        ),
    )


def test_empty_findings_emits_no_taxonomies() -> None:
    doc = build_sarif_document((), _run())
    sarif_run = doc["runs"][0]
    assert sarif_run.get("taxonomies", []) == []


def test_finding_with_cwe_attack_owasp_emits_all_three_taxa() -> None:
    finding = _finding()
    doc = build_sarif_document((finding,), _run())
    sarif_run = doc["runs"][0]
    taxonomies = sarif_run["taxonomies"]
    names = {t["name"] for t in taxonomies}
    assert names == {"CWE", "MITRE-ATTACK", "OWASP-API-Top10-2023"}
    cwe_taxa = next(t for t in taxonomies if t["name"] == "CWE")
    assert cwe_taxa["taxa"][0]["id"] == "CWE-347"
    assert "cwe.mitre.org/data/definitions/347" in cwe_taxa["taxa"][0]["helpUri"]
    attack_taxa = next(t for t in taxonomies if t["name"] == "MITRE-ATTACK")
    assert attack_taxa["taxa"][0]["id"] == "T1606.001"
    assert attack_taxa["taxa"][0]["helpUri"].endswith("/T1606/001/")
    owasp_taxa = next(t for t in taxonomies if t["name"] == "OWASP-API-Top10-2023")
    assert owasp_taxa["taxa"][0]["id"] == "API-2023-08"


def test_result_carries_taxa_references_and_properties() -> None:
    finding = _finding()
    doc = build_sarif_document((finding,), _run())
    result = doc["runs"][0]["results"][0]
    taxa_refs = result["taxa"]
    assert {ref["toolComponent"]["name"] for ref in taxa_refs} == {
        "CWE",
        "MITRE-ATTACK",
        "OWASP-API-Top10-2023",
    }
    props = result["properties"]
    assert props["cwe_id"] == "CWE-347"
    assert props["attack_id"] == "T1606.001"
    assert props["owasp_api_id"] == "API-2023-08"


def test_supported_taxonomies_listed_on_driver() -> None:
    doc = build_sarif_document((_finding(),), _run())
    driver = doc["runs"][0]["tool"]["driver"]
    names = {entry["name"] for entry in driver["supportedTaxonomies"]}
    assert "CWE" in names
    assert "MITRE-ATTACK" in names
    assert "OWASP-API-Top10-2023" in names


def test_finding_without_taxonomy_ids_skips_taxa() -> None:
    finding = _finding(cwe_id=None, attack_id=None, owasp_api_id=None)
    doc = build_sarif_document((finding,), _run())
    sarif_run = doc["runs"][0]
    assert "taxonomies" not in sarif_run
    result = sarif_run["results"][0]
    assert "taxa" not in result


def test_taxa_are_deduplicated_across_findings() -> None:
    a = _finding()
    b = _finding(cwe_id="CWE-347")  # same cwe
    doc = build_sarif_document((a, b), _run())
    cwe_taxa = next(t for t in doc["runs"][0]["taxonomies"] if t["name"] == "CWE")
    assert len(cwe_taxa["taxa"]) == 1


def test_taxa_sorted_deterministically() -> None:
    higher = _finding(cwe_id="CWE-918")
    lower = _finding(cwe_id="CWE-347")
    doc = build_sarif_document((higher, lower), _run())
    cwe_taxa = next(t for t in doc["runs"][0]["taxonomies"] if t["name"] == "CWE")
    assert [t["id"] for t in cwe_taxa["taxa"]] == ["CWE-347", "CWE-918"]
