"""Translate supply-chain typed reports into PRD §18.2 :class:`Finding` records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator

from modules.supply_chain.models import (
    ContainerReport,
    FreshnessLockfileResult,
    FreshnessReport,
    LicenseEntry,
    LicenseReport,
    OsvReport,
    PostinstallIssue,
    PostinstallReport,
)


def _evidence(id_generator: IdGenerator, artifact_path: str) -> tuple[Evidence, ...]:
    return (
        Evidence(
            id=id_generator.new("EVD"),
            type="source_ref",
            path=Path(artifact_path),
        ),
    )


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


# ---------------------------------------------------------------------------
# OSV
# ---------------------------------------------------------------------------


def findings_from_osv(
    *,
    report: OsvReport,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str = "supply_chain/vulnerabilities.json",
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    """One Finding per advisory, severity = advisory severity."""

    timestamp = _now(now)
    findings: list[Finding] = []
    for component in report.vulnerabilities:
        for advisory in component.advisories:
            cwe_id = advisory.cwe_ids[0] if advisory.cwe_ids else None
            summary = advisory.summary or "No upstream summary available."
            findings.append(
                Finding(
                    id=id_generator.new("FND"),
                    run_id=run_id,
                    module="supply_chain",
                    category="supply_chain/osv/vulnerable-dep",
                    severity=advisory.severity,
                    confidence=0.95,
                    title=f"{advisory.id} affects {component.package}@{component.version}",
                    description=summary[:8000],
                    location=FindingLocation(),
                    evidence=_evidence(id_generator, artifact_path),
                    affected_target=target_base_url,
                    recommendation=(
                        f"Upgrade {component.package} to {advisory.fixed_in}."
                        if advisory.fixed_in
                        else (
                            f"No fixed version listed yet for {advisory.id}; pin the dep to "
                            "a known-good version or remove it until a patch ships."
                        )
                    ),
                    cwe_id=cwe_id,
                    created_at=timestamp,
                )
            )
    return tuple(findings)


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


def _freshness_finding_for(
    result: FreshnessLockfileResult,
    *,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str,
    timestamp: datetime,
) -> tuple[Finding, ...]:
    out: list[Finding] = []
    if result.stale:
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="supply_chain",
                category="supply_chain/freshness/stale-lockfile",
                severity="medium",
                confidence=0.9,
                title=(
                    f"Lockfile {result.path} is {result.age_days} days old "
                    f"(threshold {result.threshold_days})"
                ),
                description=(
                    f"The lockfile at {result.path} was last modified "
                    f"{result.age_days} days ago. The configured freshness "
                    f"threshold is {result.threshold_days} days."
                ),
                location=FindingLocation(file=result.path),
                evidence=_evidence(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=(
                    "Run the package manager's install / lock command to "
                    "refresh the lockfile and commit it."
                ),
                cwe_id="CWE-1357",
                created_at=timestamp,
            )
        )
    if result.manifest_drift:
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="supply_chain",
                category="supply_chain/freshness/manifest-drift",
                severity="medium",
                confidence=0.85,
                title=f"Manifest drift detected in {result.path}",
                description=(
                    "The following direct dependencies are declared in the "
                    "manifest but missing from the lockfile:\n  - "
                    + "\n  - ".join(result.manifest_drift[:30])
                ),
                location=FindingLocation(file=result.path),
                evidence=_evidence(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=(
                    "Run the package manager's install command (npm i / "
                    "pnpm i / uv sync / poetry lock) and commit the "
                    "regenerated lockfile."
                ),
                cwe_id="CWE-1357",
                created_at=timestamp,
            )
        )
    return tuple(out)


def findings_from_freshness(
    *,
    report: FreshnessReport,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str = "supply_chain/freshness.json",
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = _now(now)
    out: list[Finding] = []
    for result in report.lockfiles:
        out.extend(
            _freshness_finding_for(
                result,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_path,
                timestamp=timestamp,
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Postinstall
# ---------------------------------------------------------------------------


_POSTINSTALL_CATEGORIES = {
    "npm": {
        "default": "supply_chain/postinstall/network-call",
        "fs-write": "supply_chain/postinstall/fs-write",
    },
    "python": {
        "default": "supply_chain/postinstall/python-exec",
    },
}


def _category_for_postinstall(issue: PostinstallIssue) -> str:
    if issue.ecosystem == "npm":
        if issue.pattern.startswith("fs-write:"):
            return _POSTINSTALL_CATEGORIES["npm"]["fs-write"]
        return _POSTINSTALL_CATEGORIES["npm"]["default"]
    return _POSTINSTALL_CATEGORIES["python"]["default"]


def findings_from_postinstall(
    *,
    report: PostinstallReport,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str = "supply_chain/postinstall_findings.json",
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = _now(now)
    findings: list[Finding] = []
    for issue in report.issues:
        category = _category_for_postinstall(issue)
        findings.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="supply_chain",
                category=category,
                severity=issue.severity,
                confidence=0.85,
                title=(
                    f"Postinstall hook {issue.hook!r} in {issue.package} "
                    f"matches suspicious pattern {issue.pattern!r}"
                ),
                description=(
                    f"Detected pattern {issue.pattern!r} inside {issue.path} "
                    f"({issue.ecosystem}/{issue.hook}).\n\nSnippet: "
                    f"{issue.snippet[:1500]}"
                ),
                location=FindingLocation(file=issue.path),
                evidence=_evidence(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=(
                    "Review the upstream package; pin to an audited version "
                    "or run installs with --ignore-scripts (npm) / "
                    "--only-binary (pip) so untrusted hooks never execute."
                ),
                cwe_id="CWE-506",
                created_at=timestamp,
            )
        )
    return tuple(findings)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


def findings_from_container(
    *,
    report: ContainerReport,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str = "supply_chain/container.json",
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = _now(now)
    out: list[Finding] = []
    if report.skipped and report.scanner == "none":
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="supply_chain",
                category="supply_chain/container/scanner-not-installed",
                severity="info",
                confidence=1.0,
                title="Container scanner not installed",
                description=(
                    report.skipped_reason
                    or "No container scanner is on PATH; the container check was skipped."
                ),
                location=FindingLocation(),
                evidence=_evidence(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=(
                    "Install Trivy (https://aquasecurity.github.io/trivy) "
                    "or Grype (https://github.com/anchore/grype). SentinelQA "
                    "never auto-installs scanners."
                ),
                created_at=timestamp,
            )
        )
        return tuple(out)
    for vuln in report.findings:
        cwe_id = vuln.cwe_ids[0] if vuln.cwe_ids else None
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="supply_chain",
                category="supply_chain/container/cve",
                severity=vuln.severity,
                confidence=0.9,
                title=f"{vuln.vuln_id} in {vuln.package}@{vuln.installed_version}",
                description=(vuln.description or vuln.title or "(no description)")[:8000],
                location=FindingLocation(),
                evidence=_evidence(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=(
                    f"Upgrade {vuln.package} to {vuln.fixed_version}."
                    if vuln.fixed_version
                    else f"No fix listed yet for {vuln.vuln_id}; rebuild the image from "
                    "a patched base or remove the affected package."
                ),
                cwe_id=cwe_id,
                created_at=timestamp,
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Licenses
# ---------------------------------------------------------------------------


def _license_finding_for(
    entry: LicenseEntry,
    *,
    unknown_severity: Severity,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str,
    timestamp: datetime,
) -> Finding | None:
    if entry.verdict == "deny":
        return Finding(
            id=id_generator.new("FND"),
            run_id=run_id,
            module="supply_chain",
            category="supply_chain/license/deny",
            severity="high",
            confidence=0.95,
            title=(
                f"{entry.name}@{entry.version} carries a denied license "
                f"({', '.join(entry.spdx_ids) or 'unspecified'})"
            ),
            description=entry.recommendation or "(no recommendation)",
            location=FindingLocation(),
            evidence=_evidence(id_generator, artifact_path),
            affected_target=target_base_url,
            recommendation=entry.recommendation,
            created_at=timestamp,
        )
    if entry.verdict == "unknown":
        return Finding(
            id=id_generator.new("FND"),
            run_id=run_id,
            module="supply_chain",
            category="supply_chain/license/unknown",
            severity=unknown_severity,
            confidence=0.75,
            title=f"{entry.name}@{entry.version} has no declared SPDX license",
            description=entry.recommendation or "(no recommendation)",
            location=FindingLocation(),
            evidence=_evidence(id_generator, artifact_path),
            affected_target=target_base_url,
            recommendation=entry.recommendation,
            created_at=timestamp,
        )
    return None


def findings_from_licenses(
    *,
    report: LicenseReport,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str = "supply_chain/licenses.json",
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = _now(now)
    out: list[Finding] = []
    for entry in report.entries:
        finding = _license_finding_for(
            entry,
            unknown_severity=report.unknown_severity,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
        if finding is not None:
            out.append(finding)
    return tuple(out)


__all__ = [
    "findings_from_container",
    "findings_from_freshness",
    "findings_from_licenses",
    "findings_from_osv",
    "findings_from_postinstall",
]
