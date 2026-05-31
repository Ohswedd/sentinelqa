"""Targeted edge-case coverage for container + lockfile parsers."""

from __future__ import annotations

import subprocess

from modules.supply_chain.container import (
    parse_grype_report,
    parse_trivy_report,
    scan_container,
)

# ---------------------------------------------------------------------------
# Trivy parser — defensive shapes
# ---------------------------------------------------------------------------


def test_parse_trivy_skips_non_dict_results() -> None:
    payload = {"Results": ["not a dict", 123]}
    assert parse_trivy_report(payload) == ()


def test_parse_trivy_skips_non_dict_vulns() -> None:
    payload = {"Results": [{"Vulnerabilities": ["not a dict", 1]}]}
    assert parse_trivy_report(payload) == ()


def test_parse_trivy_skips_when_non_string_ids() -> None:
    payload = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "ok",
                        "PkgName": "openssl",
                        "InstalledVersion": "3.0",
                        # FixedVersion of wrong type — should default to None.
                        "FixedVersion": 12,
                        "Severity": "HIGH",
                    },
                ]
            }
        ]
    }
    results = parse_trivy_report(payload)
    assert len(results) == 1
    assert results[0].fixed_version is None


# ---------------------------------------------------------------------------
# Grype parser — defensive shapes
# ---------------------------------------------------------------------------


def test_parse_grype_skips_non_dict_matches() -> None:
    payload = {"matches": ["string", 1, None]}
    assert parse_grype_report(payload) == ()


def test_parse_grype_skips_non_dict_vulnerability_or_artifact() -> None:
    payload = {"matches": [{"vulnerability": "string", "artifact": {}}]}
    assert parse_grype_report(payload) == ()
    payload = {"matches": [{"vulnerability": {"id": "ok"}, "artifact": "string"}]}
    assert parse_grype_report(payload) == ()


def test_parse_grype_skips_non_string_package_version() -> None:
    payload = {
        "matches": [
            {
                "vulnerability": {"id": "ok"},
                "artifact": {"name": 123, "version": "1.0"},
            },
        ]
    }
    assert parse_grype_report(payload) == ()


def test_parse_grype_handles_versions_list_with_non_strings() -> None:
    payload = {
        "matches": [
            {
                "vulnerability": {
                    "id": "ok",
                    "severity": "Medium",
                    "fix": {"versions": [None, "1.2.3"]},
                },
                "artifact": {"name": "p", "version": "1.0"},
            },
        ]
    }
    results = parse_grype_report(payload)
    assert results[0].fixed_version is None


def test_scan_container_handles_unset_max_findings_below_zero() -> None:
    """Negative caps should clamp to "no cap"."""

    payload = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-1",
                        "PkgName": "p",
                        "InstalledVersion": "1.0",
                        "Severity": "MEDIUM",
                    }
                ]
            }
        ]
    }

    def fake_run(_argv):  # type: ignore[no-untyped-def]
        import json as _json

        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=_json.dumps(payload),
            stderr="",
        )

    report = scan_container(
        image="example:tag",
        max_findings=0,
        scanner="trivy",
        run_callable=fake_run,
    )
    assert report.cap_reached is False
    assert len(report.findings) == 1
