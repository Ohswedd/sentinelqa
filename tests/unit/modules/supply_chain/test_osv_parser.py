"""OSV response parser tests."""

from __future__ import annotations

from modules.supply_chain.models import SbomComponent
from modules.supply_chain.osv import (
    parse_osv_response_for_component,
    severity_from_cvss,
)


def _component(name: str = "requests", version: str = "2.31.0") -> SbomComponent:
    return SbomComponent(
        name=name,
        version=version,
        ecosystem="PyPI",
        purl=f"pkg:pypi/{name}@{version}",
    )


def test_severity_from_cvss_bands() -> None:
    assert severity_from_cvss(9.5) == "critical"
    assert severity_from_cvss(7.0) == "high"
    assert severity_from_cvss(5.5) == "medium"
    assert severity_from_cvss(1.0) == "low"
    assert severity_from_cvss(0.0) == "info"
    assert severity_from_cvss(None) == "medium"


def test_parse_osv_extracts_advisory_basics() -> None:
    response = [
        {
            "id": "GHSA-xxxx-yyyy-zzzz",
            "summary": "Test vuln summary",
            "severity": [{"type": "CVSS_V3", "score": "9.1"}],
            "database_specific": {"cwe_ids": ["CWE-79", "CWE-200"]},
            "affected": [
                {
                    "ranges": [
                        {
                            "events": [
                                {"introduced": "0"},
                                {"fixed": "2.32.0"},
                            ]
                        }
                    ]
                }
            ],
        }
    ]
    result = parse_osv_response_for_component(_component(), response)
    assert len(result.advisories) == 1
    advisory = result.advisories[0]
    assert advisory.id == "GHSA-xxxx-yyyy-zzzz"
    assert advisory.severity == "critical"
    assert advisory.cwe_ids == ("CWE-79", "CWE-200")
    assert advisory.fixed_in == "2.32.0"
    assert "Test vuln summary" in advisory.summary


def test_parse_osv_handles_missing_severity() -> None:
    response = [{"id": "GHSA-only", "summary": "x"}]
    result = parse_osv_response_for_component(_component(), response)
    assert result.advisories[0].severity == "medium"


def test_parse_osv_skips_entries_without_id() -> None:
    response = [{"summary": "no id"}, {"id": "GHSA-real", "summary": "y"}]
    result = parse_osv_response_for_component(_component(), response)
    assert [a.id for a in result.advisories] == ["GHSA-real"]


def test_parse_osv_handles_vector_severity_string() -> None:
    response = [
        {
            "id": "GHSA-vec",
            "summary": "vector test",
            "severity": [
                {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
            ],
        }
    ]
    result = parse_osv_response_for_component(_component(), response)
    # Vector strings don't yield a numeric score, so we default to medium.
    assert result.advisories[0].severity == "medium"


def test_parse_osv_drops_non_cwe_ids() -> None:
    response = [
        {
            "id": "GHSA-cwe-shape",
            "summary": "z",
            "database_specific": {"cwe_ids": ["CWE-79", "not-a-cwe", 123, "CWE-22"]},
        }
    ]
    result = parse_osv_response_for_component(_component(), response)
    assert result.advisories[0].cwe_ids == ("CWE-79", "CWE-22")
