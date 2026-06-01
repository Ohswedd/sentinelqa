"""Container scanner — Trivy JSON parser."""

from __future__ import annotations

import json
import subprocess

from modules.supply_chain.container import parse_trivy_report, scan_container

_TRIVY_FIXTURE = {
    "Results": [
        {
            "Target": "image:latest (debian 12)",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2024-1234",
                    "PkgName": "openssl",
                    "InstalledVersion": "3.0.1-1",
                    "FixedVersion": "3.0.2-1",
                    "Severity": "HIGH",
                    "Title": "openssl issue",
                    "Description": "details",
                    "CweIDs": ["CWE-79"],
                },
                {
                    "VulnerabilityID": "CVE-2024-2000",
                    "PkgName": "libxml2",
                    "InstalledVersion": "2.10.4",
                    "Severity": "CRITICAL",
                },
            ],
        }
    ]
}


def test_parse_trivy_emits_vulnerabilities() -> None:
    results = parse_trivy_report(_TRIVY_FIXTURE)
    assert len(results) == 2
    openssl = next(r for r in results if r.package == "openssl")
    assert openssl.severity == "high"
    assert openssl.fixed_version == "3.0.2-1"
    assert "CWE-79" in openssl.cwe_ids


def test_parse_trivy_handles_missing_results_key() -> None:
    assert parse_trivy_report({}) == ()
    assert parse_trivy_report({"Results": "not a list"}) == ()


def test_parse_trivy_skips_malformed_vulns() -> None:
    payload = {
        "Results": [
            {
                "Vulnerabilities": [
                    {"VulnerabilityID": 123, "PkgName": "x", "InstalledVersion": "1"},
                    {"VulnerabilityID": "ok", "PkgName": "y", "InstalledVersion": "1"},
                ]
            }
        ]
    }
    results = parse_trivy_report(payload)
    assert [r.vuln_id for r in results] == ["ok"]


def test_scan_container_returns_cap_reached(tmp_path) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": f"CVE-{i:04d}",
                        "PkgName": "pkg",
                        "InstalledVersion": "1.0",
                        "Severity": "MEDIUM",
                    }
                    for i in range(5)
                ]
            }
        ]
    }

    def fake_run(_argv):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )

    report = scan_container(
        image="example:tag",
        max_findings=2,
        scanner="trivy",
        run_callable=fake_run,
    )
    assert report.cap_reached is True
    assert len(report.findings) == 2
