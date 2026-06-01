"""Final targeted coverage gap closers for."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

from modules.supply_chain.container import (
    _cap,
    _map_severity,
    grype_command,
    scan_container,
    trivy_command,
)
from modules.supply_chain.models import (
    ContainerVulnerability,
    OsvReport,
    SbomComponent,
    SbomDocument,
)
from modules.supply_chain.osv import (
    _coerce_cvss,
    _extract_cwes,
    _extract_fixed_in,
    _RateLimiter,
    query_osv,
    run_osv_lookup_from_sbom,
    serialize_osv_report,
)
from modules.supply_chain.postinstall import scan_npm_packages


def test_map_severity_handles_unknown_labels() -> None:
    assert _map_severity(None) == "info"
    assert _map_severity("UNKNOWN") == "info"
    assert _map_severity("Bogus") == "info"
    assert _map_severity("CRITICAL") == "critical"
    assert _map_severity("LOW") == "low"


def test_cap_preserves_severity_ordering() -> None:
    findings = (
        ContainerVulnerability(
            scanner="trivy",
            vuln_id=f"CVE-{i}",
            package="p",
            installed_version="1.0",
            severity=sev,  # type: ignore[arg-type]
        )
        for i, sev in enumerate(("low", "critical", "medium", "high"))
    )
    capped, reached = _cap(findings, max_findings=2)
    severities = [f.severity for f in capped]
    assert reached is True
    assert severities == ["critical", "high"]


def test_trivy_and_grype_command_shapes() -> None:
    trivy = trivy_command("example:tag")
    assert trivy.binary == "trivy" and "--format" in trivy.argv
    grype = grype_command("example:tag")
    assert grype.binary == "grype" and "json" in grype.argv


def test_scan_container_rejects_non_dict_payload() -> None:
    def fake_run(_argv):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps([1, 2, 3]), stderr=""
        )

    report = scan_container(image="x:tag", scanner="trivy", run_callable=fake_run)
    assert report.skipped is True
    assert "unexpected JSON shape" in (report.skipped_reason or "")


def test_coerce_cvss_handles_each_branch() -> None:
    assert _coerce_cvss(None) is None
    assert _coerce_cvss(3.14) == 3.14
    assert _coerce_cvss("4.0") == 4.0
    assert _coerce_cvss("CVSS:3.1/AV:N/AC:L") is None
    assert _coerce_cvss(["not", "numeric"]) is None


def test_extract_cwes_handles_non_lists() -> None:
    assert _extract_cwes(None) == ()
    assert _extract_cwes({"cwe_ids": None}) == ()
    assert _extract_cwes({"cwe_ids": ["CWE-1", "bad"]}) == ("CWE-1",)


def test_extract_fixed_in_returns_first_event() -> None:
    affected = [
        {"ranges": [{"events": [{"introduced": "0"}]}]},
        {"ranges": [{"events": [{"fixed": "1.2.3"}]}]},
    ]
    assert _extract_fixed_in(affected) == "1.2.3"
    assert _extract_fixed_in(None) is None
    assert _extract_fixed_in([{"ranges": []}]) is None


def test_rate_limiter_no_rate_returns_zero_sleep() -> None:
    rl = _RateLimiter(rate_limit_rps=0.0)
    assert rl.sleep_for(0.0) == 0.0


def test_serialize_osv_report_round_trip() -> None:
    report = OsvReport(
        queried_at=datetime(2026, 5, 31, tzinfo=UTC),
        components_count=0,
        vulnerabilities=(),
    )
    payload = serialize_osv_report(report)
    assert payload["components_count"] == 0
    assert payload["schema_version"] == "1"


def test_run_osv_lookup_with_empty_sbom_returns_clean_report() -> None:
    sbom = SbomDocument(
        generated_at=datetime(2026, 5, 31, tzinfo=UTC),
        project_name="empty",
        lockfiles=(),
        components_count=0,
    )
    report = run_osv_lookup_from_sbom(sbom=sbom, enabled=True)
    assert report.components_count == 0
    assert report.skipped is False


def test_query_osv_empty_components_short_circuit() -> None:
    # No transport, no http call — should return immediately.
    report = query_osv(components=(), rate_limit_rps=10.0)
    assert report.skipped is False
    assert report.components_count == 0


def test_query_osv_empty_results_handles_response_shape() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": "wrong-shape"})

    report = query_osv(
        components=(
            SbomComponent(
                name="requests",
                version="2.31.0",
                ecosystem="PyPI",
                purl="pkg:pypi/requests@2.31.0",
            ),
        ),
        rate_limit_rps=10000.0,
        transport=httpx.MockTransport(handler),
    )
    assert report.components_count == 1
    # Wrong-shape results → no vulnerabilities, no skipped.
    assert report.vulnerabilities == ()


def test_scan_npm_packages_skips_malformed_package_json(tmp_path: Path) -> None:
    pkg_path = tmp_path / "node_modules" / "weird" / "package.json"
    pkg_path.parent.mkdir(parents=True)
    pkg_path.write_text("not json {", encoding="utf-8")
    # Plus a list-shape (valid JSON but not a dict).
    list_path = tmp_path / "node_modules" / "list" / "package.json"
    list_path.parent.mkdir(parents=True)
    list_path.write_text("[1,2,3]", encoding="utf-8")
    # Plus a package whose scripts field is the wrong shape.
    wrong_scripts = tmp_path / "node_modules" / "wrong" / "package.json"
    wrong_scripts.parent.mkdir(parents=True)
    wrong_scripts.write_text(
        json.dumps({"name": "wrong", "scripts": "not-a-dict"}), encoding="utf-8"
    )
    assert scan_npm_packages(tmp_path / "node_modules") == ()
