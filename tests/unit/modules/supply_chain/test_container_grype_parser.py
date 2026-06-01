"""Container scanner — Grype JSON parser."""

from __future__ import annotations

from modules.supply_chain.container import parse_grype_report

_GRYPE_FIXTURE = {
    "matches": [
        {
            "vulnerability": {
                "id": "CVE-2024-1234",
                "severity": "High",
                "description": "openssl issue",
                "fix": {"versions": ["3.0.2-1"]},
                "cwes": ["CWE-79"],
            },
            "artifact": {"name": "openssl", "version": "3.0.1-1"},
        },
        {
            "vulnerability": {
                "id": "CVE-2024-9999",
                "severity": "Critical",
            },
            "artifact": {"name": "libxml2", "version": "2.10.4"},
        },
    ]
}


def test_parse_grype_emits_vulnerabilities() -> None:
    results = parse_grype_report(_GRYPE_FIXTURE)
    assert len(results) == 2
    openssl = next(r for r in results if r.package == "openssl")
    assert openssl.severity == "high"
    assert openssl.fixed_version == "3.0.2-1"
    assert "CWE-79" in openssl.cwe_ids


def test_parse_grype_handles_missing_matches() -> None:
    assert parse_grype_report({}) == ()
    assert parse_grype_report({"matches": "wrong"}) == ()


def test_parse_grype_skips_malformed_entries() -> None:
    payload = {
        "matches": [
            {"vulnerability": {"id": 1}, "artifact": {"name": "x"}},  # bad id type
            {
                "vulnerability": {"id": "ok"},
                "artifact": {"name": "y", "version": "1.0"},
            },
        ]
    }
    results = parse_grype_report(payload)
    assert [r.vuln_id for r in results] == ["ok"]
