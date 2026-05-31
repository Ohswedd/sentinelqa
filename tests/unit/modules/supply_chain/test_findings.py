"""Findings translator tests (Phase 33 — all six checks)."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.supply_chain.findings import (
    findings_from_container,
    findings_from_freshness,
    findings_from_licenses,
    findings_from_osv,
    findings_from_postinstall,
)
from modules.supply_chain.models import (
    ContainerReport,
    ContainerVulnerability,
    FreshnessLockfileResult,
    FreshnessReport,
    LicenseEntry,
    LicenseReport,
    OsvAdvisory,
    OsvComponentResult,
    OsvReport,
    PostinstallIssue,
    PostinstallReport,
)


def _ids() -> IdGenerator:
    return IdGenerator()


def _ts() -> datetime:
    return datetime(2026, 5, 31, tzinfo=UTC)


def _run_id() -> str:
    return IdGenerator().new("RUN")


def test_findings_from_osv_emits_one_per_advisory() -> None:
    report = OsvReport(
        queried_at=_ts(),
        components_count=1,
        vulnerabilities=(
            OsvComponentResult(
                package="requests",
                version="2.31.0",
                ecosystem="PyPI",
                advisories=(
                    OsvAdvisory(
                        id="GHSA-1",
                        severity="high",
                        cwe_ids=("CWE-22",),
                        fixed_in="2.32.0",
                        summary="path traversal",
                    ),
                    OsvAdvisory(id="GHSA-2", severity="medium"),
                ),
            ),
        ),
    )
    findings = findings_from_osv(
        report=report,
        run_id=_run_id(),
        target_base_url="http://localhost:3000",
        id_generator=_ids(),
        now=_ts(),
    )
    assert len(findings) == 2
    assert findings[0].cwe_id == "CWE-22"
    assert findings[0].recommendation and "2.32.0" in findings[0].recommendation
    # Second advisory had no fixed_in -> recommendation uses fallback wording.
    assert findings[1].recommendation and "pin the dep" in findings[1].recommendation


def test_findings_from_freshness_stale_and_drift() -> None:
    report = FreshnessReport(
        checked_at=_ts(),
        threshold_days=90,
        lockfiles=(
            FreshnessLockfileResult(
                path="package-lock.json",
                kind="package-lock.json",
                age_days=200,
                stale=True,
                threshold_days=90,
                manifest_drift=("foo", "bar"),
            ),
            FreshnessLockfileResult(
                path="uv.lock",
                kind="uv.lock",
                age_days=10,
                stale=False,
                threshold_days=90,
                manifest_drift=(),
            ),
        ),
    )
    findings = findings_from_freshness(
        report=report,
        run_id=_run_id(),
        target_base_url="http://localhost:3000",
        id_generator=_ids(),
        now=_ts(),
    )
    # Stale + drift on first lockfile -> 2 findings; clean second lockfile -> 0.
    categories = {f.category for f in findings}
    assert "supply_chain/freshness/stale-lockfile" in categories
    assert "supply_chain/freshness/manifest-drift" in categories
    assert all(f.cwe_id == "CWE-1357" for f in findings)


def test_findings_from_postinstall_categories() -> None:
    report = PostinstallReport(
        scanned_packages=2,
        issues=(
            PostinstallIssue(
                ecosystem="npm",
                package="badnet",
                path="/p/package.json",
                hook="postinstall",
                snippet="curl https://x",
                pattern="curl",
                severity="high",
            ),
            PostinstallIssue(
                ecosystem="npm",
                package="fswrite",
                path="/p/package.json",
                hook="postinstall",
                snippet="echo > /etc/x",
                pattern="fs-write:/etc/",
                severity="medium",
            ),
            PostinstallIssue(
                ecosystem="python",
                package="pyevil",
                path="/p/setup.py",
                hook="setup.py",
                snippet="import subprocess",
                pattern="import:subprocess",
                severity="high",
            ),
        ),
    )
    findings = findings_from_postinstall(
        report=report,
        run_id=_run_id(),
        target_base_url="http://localhost:3000",
        id_generator=_ids(),
        now=_ts(),
    )
    categories = [f.category for f in findings]
    assert "supply_chain/postinstall/network-call" in categories
    assert "supply_chain/postinstall/fs-write" in categories
    assert "supply_chain/postinstall/python-exec" in categories
    assert all(f.cwe_id == "CWE-506" for f in findings)


def test_findings_from_container_includes_skipped_recommendation() -> None:
    report = ContainerReport(
        image="example:tag",
        scanner="none",
        findings=(),
        skipped=True,
        skipped_reason="container-scanner-not-installed: install Trivy or Grype",
    )
    findings = findings_from_container(
        report=report,
        run_id=_run_id(),
        target_base_url="http://localhost:3000",
        id_generator=_ids(),
        now=_ts(),
    )
    assert len(findings) == 1
    assert findings[0].category == "supply_chain/container/scanner-not-installed"
    assert findings[0].severity == "info"


def test_findings_from_container_vulnerabilities() -> None:
    report = ContainerReport(
        image="example:tag",
        scanner="trivy",
        findings=(
            ContainerVulnerability(
                scanner="trivy",
                vuln_id="CVE-1",
                package="openssl",
                installed_version="3.0.1",
                fixed_version="3.0.2",
                severity="high",
                cwe_ids=("CWE-79",),
                title="t",
                description="d",
            ),
            ContainerVulnerability(
                scanner="trivy",
                vuln_id="CVE-2",
                package="libxml2",
                installed_version="2.10",
                fixed_version=None,
                severity="medium",
            ),
        ),
    )
    findings = findings_from_container(
        report=report,
        run_id=_run_id(),
        target_base_url="http://localhost:3000",
        id_generator=_ids(),
        now=_ts(),
    )
    assert len(findings) == 2
    assert findings[0].cwe_id == "CWE-79"
    assert findings[1].recommendation and "No fix listed" in findings[1].recommendation


def test_findings_from_licenses_deny_and_unknown() -> None:
    report = LicenseReport(
        allow=("MIT",),
        deny=("AGPL-3.0-only",),
        unknown_severity="medium",
        entries=(
            LicenseEntry(
                name="badlib",
                version="1.0.0",
                ecosystem="npm",
                spdx_ids=("AGPL-3.0-only",),
                verdict="deny",
                recommendation="remove",
            ),
            LicenseEntry(
                name="orphan",
                version="1.0.0",
                ecosystem="npm",
                spdx_ids=(),
                verdict="unknown",
                recommendation="declare license",
            ),
            LicenseEntry(
                name="good",
                version="1.0.0",
                ecosystem="npm",
                spdx_ids=("MIT",),
                verdict="allow",
                recommendation="",
            ),
        ),
    )
    findings = findings_from_licenses(
        report=report,
        run_id=_run_id(),
        target_base_url="http://localhost:3000",
        id_generator=_ids(),
        now=_ts(),
    )
    assert len(findings) == 2  # deny + unknown (allow → no finding)
    severities = {f.severity for f in findings}
    assert "high" in severities  # deny
    assert "medium" in severities  # unknown @ medium
