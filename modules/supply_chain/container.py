"""Container image scanner adapter.

Wraps Trivy (https://aquasecurity.github.io/trivy) and Grype
(https://github.com/anchore/grype) — both are widely-deployed
defensive scanners that produce machine-readable JSON. Either binary
on ``PATH`` is sufficient; we prefer Trivy when both are present
(richer CVSS metadata).

Safety boundary:

- The scanner runs only against the configured
 ``policy.supply_chain.container.image``; we never pull random images,
 iterate registries, or scan running containers.
- We never pass ``--ignore-policy`` / ``--insecure`` / any auth
 override that would let the scanner reach into a private registry
 unannounced.
- When neither Trivy nor Grype is on ``PATH``, the report is
 ``skipped`` with a clear ``info``-severity recommendation to install
 one. We never silently mark the run "passed".

The cap (``max_findings``, default 200) is enforced after parsing so
the report stays consumable on CVE-heavy base images.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from engine.domain.finding import Severity

from modules.supply_chain.models import (
    ContainerReport,
    ContainerScanner,
    ContainerVulnerability,
)

DEFAULT_MAX_FINDINGS = 200


@dataclass(frozen=True, slots=True)
class ScannerInvocation:
    """Description of one scanner subprocess call."""

    binary: str
    argv: tuple[str, ...]


_TRIVY_SEVERITY_MAP: dict[str, Severity] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNKNOWN": "info",
    "NEGLIGIBLE": "info",
}


def _map_severity(label: str | None) -> Severity:
    if not label:
        return "info"
    return _TRIVY_SEVERITY_MAP.get(label.upper(), "info")


def _coerce_cwes(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.startswith("CWE-"))


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_trivy_report(payload: dict[str, Any]) -> tuple[ContainerVulnerability, ...]:
    """Translate Trivy's JSON shape into our findings."""

    out: list[ContainerVulnerability] = []
    results = payload.get("Results")
    if not isinstance(results, list):
        return ()
    for result in results:
        if not isinstance(result, dict):
            continue
        for vuln in result.get("Vulnerabilities") or ():
            if not isinstance(vuln, dict):
                continue
            vuln_id = vuln.get("VulnerabilityID")
            package = vuln.get("PkgName")
            installed = vuln.get("InstalledVersion")
            if not all(isinstance(x, str) for x in (vuln_id, package, installed)):
                continue
            fixed = vuln.get("FixedVersion")
            fixed_str = fixed if isinstance(fixed, str) and fixed else None
            severity = _map_severity(vuln.get("Severity"))
            out.append(
                ContainerVulnerability(
                    scanner="trivy",
                    vuln_id=str(vuln_id),
                    package=str(package),
                    installed_version=str(installed),
                    fixed_version=fixed_str,
                    severity=severity,
                    cwe_ids=_coerce_cwes(vuln.get("CweIDs")),
                    title=str(vuln.get("Title") or "")[:300],
                    description=str(vuln.get("Description") or "")[:4000],
                )
            )
    return tuple(out)


def parse_grype_report(payload: dict[str, Any]) -> tuple[ContainerVulnerability, ...]:
    """Translate Grype's JSON shape into our findings."""

    out: list[ContainerVulnerability] = []
    matches = payload.get("matches")
    if not isinstance(matches, list):
        return ()
    for match in matches:
        if not isinstance(match, dict):
            continue
        vulnerability = match.get("vulnerability")
        artifact = match.get("artifact")
        if not isinstance(vulnerability, dict) or not isinstance(artifact, dict):
            continue
        vuln_id = vulnerability.get("id")
        if not isinstance(vuln_id, str):
            continue
        package = artifact.get("name")
        installed = artifact.get("version")
        if not isinstance(package, str) or not isinstance(installed, str):
            continue
        fix = vulnerability.get("fix")
        fixed_str: str | None = None
        if isinstance(fix, dict):
            versions = fix.get("versions")
            if isinstance(versions, list) and versions and isinstance(versions[0], str):
                fixed_str = versions[0]
        severity = _map_severity(vulnerability.get("severity"))
        out.append(
            ContainerVulnerability(
                scanner="grype",
                vuln_id=vuln_id,
                package=package,
                installed_version=installed,
                fixed_version=fixed_str,
                severity=severity,
                cwe_ids=_coerce_cwes(vulnerability.get("cwes")),
                title=str(vulnerability.get("description") or "")[:300],
                description=str(vulnerability.get("description") or "")[:4000],
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


def trivy_command(image: str) -> ScannerInvocation:
    return ScannerInvocation(
        binary="trivy",
        argv=("trivy", "image", "--format", "json", "--quiet", image),
    )


def grype_command(image: str) -> ScannerInvocation:
    return ScannerInvocation(
        binary="grype",
        argv=("grype", image, "-o", "json"),
    )


def select_scanner(
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> ContainerScanner:
    """Return whichever scanner is on ``PATH`` (prefer Trivy)."""

    if which("trivy") is not None:
        return "trivy"
    if which("grype") is not None:
        return "grype"
    return "none"


RunCallable = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )


def _cap(
    findings: Iterable[ContainerVulnerability],
    max_findings: int,
) -> tuple[tuple[ContainerVulnerability, ...], bool]:
    """Cap the list while preserving severity ordering (critical first)."""

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_list = sorted(
        findings,
        key=lambda finding: (
            severity_order.get(finding.severity, 5),
            finding.package,
            finding.vuln_id,
        ),
    )
    if max_findings <= 0 or len(sorted_list) <= max_findings:
        return tuple(sorted_list), False
    return tuple(sorted_list[:max_findings]), True


def scan_container(
    *,
    image: str | None,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    scanner: ContainerScanner | None = None,
    run_callable: RunCallable | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> ContainerReport:
    """Run the configured container scanner and return a typed report.

    When ``image`` is ``None``, ``scanner`` resolves to ``"none"``, or
    the subprocess call returns no parseable JSON, the report is
    ``skipped`` with a clear reason — the README explicitly
    forbids fabricating findings or marking the run "passed".
    """

    if image is None:
        return ContainerReport(
            image=None,
            scanner="none",
            findings=(),
            skipped=True,
            skipped_reason="policy.supply_chain.container.image is not set",
        )

    selected = scanner or select_scanner(which=which)
    if selected == "none":
        return ContainerReport(
            image=image,
            scanner="none",
            findings=(),
            skipped=True,
            skipped_reason=(
                "container-scanner-not-installed: install Trivy "
                "(https://aquasecurity.github.io/trivy) or Grype "
                "(https://github.com/anchore/grype) to enable this check"
            ),
        )

    invocation = trivy_command(image) if selected == "trivy" else grype_command(image)
    runner = run_callable or _default_run
    try:
        result = runner(invocation.argv)
    except (FileNotFoundError, OSError) as exc:
        return ContainerReport(
            image=image,
            scanner=selected,
            findings=(),
            skipped=True,
            skipped_reason=f"{selected} invocation failed: {type(exc).__name__}: {exc}"[:2000],
        )

    stdout = (result.stdout or "").strip()
    if not stdout:
        return ContainerReport(
            image=image,
            scanner=selected,
            findings=(),
            skipped=True,
            skipped_reason=f"{selected} returned no JSON (stderr: {result.stderr[:500]!r})",
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return ContainerReport(
            image=image,
            scanner=selected,
            findings=(),
            skipped=True,
            skipped_reason=f"{selected} returned unparseable JSON: {exc}"[:2000],
        )

    if not isinstance(payload, dict):
        return ContainerReport(
            image=image,
            scanner=selected,
            findings=(),
            skipped=True,
            skipped_reason=f"{selected} returned unexpected JSON shape",
        )

    vulns = parse_trivy_report(payload) if selected == "trivy" else parse_grype_report(payload)
    capped, cap_reached = _cap(vulns, max_findings)
    return ContainerReport(
        image=image,
        scanner=selected,
        findings=capped,
        cap_reached=cap_reached,
    )


__all__ = [
    "DEFAULT_MAX_FINDINGS",
    "ScannerInvocation",
    "grype_command",
    "parse_grype_report",
    "parse_trivy_report",
    "scan_container",
    "select_scanner",
    "trivy_command",
]
