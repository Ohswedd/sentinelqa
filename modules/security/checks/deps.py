"""Dependency-scanner adapters.

Each adapter shells out to a real tool (``pip-audit``, ``npm audit``,
``osv-scanner``) and normalizes its JSON output into
:class:`SecurityIssue` records under the ``SEC-DEPS-VULNERABLE`` rule.

Adapters are no-ops when:

- The corresponding tool is not on ``$PATH``. The ``doctor``
 command (extended below) surfaces missing tools to the user.
- The matching lockfile (``requirements.txt`` / ``poetry.lock`` /
 ``uv.lock`` / ``package-lock.json`` / ``pnpm-lock.yaml`` /
 ``yarn.lock``) is absent.

Each adapter accepts an optional ``run`` callable so unit tests can
inject canned JSON without spawning subprocesses.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.policy.audit_log import write_audit_entry

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "dependency_scan"


# ---------------------------------------------------------------------
# Run-callable used by adapters; tests inject a stub.
# ---------------------------------------------------------------------

RunResult = tuple[int, str, str]
RunCallable = Callable[[list[str], Path], RunResult]


def _default_run(cmd: list[str], cwd: Path) -> RunResult:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdapterReport:
    """Result of one adapter invocation."""

    scanner: str
    available: bool
    """The tool is on ``$PATH`` AND the relevant lockfile exists."""

    issues: tuple[SecurityIssue, ...] = ()
    skipped_reason: str | None = None


def _binary_available(name: str) -> bool:
    return shutil.which(name) is not None


def _pip_audit(
    *,
    run: RunCallable,
    cwd: Path,
) -> AdapterReport:
    if not _binary_available("pip-audit"):
        return AdapterReport(
            scanner="pip-audit",
            available=False,
            skipped_reason="pip-audit not on PATH",
        )
    lockfiles = [cwd / "requirements.txt", cwd / "poetry.lock", cwd / "uv.lock"]
    if not any(p.exists() for p in lockfiles):
        return AdapterReport(
            scanner="pip-audit",
            available=False,
            skipped_reason="no requirements.txt / poetry.lock / uv.lock found",
        )
    rc, stdout, _stderr = run(["pip-audit", "--format", "json"], cwd)
    # pip-audit exits non-zero when vulns found; 0 + empty means clean.
    if rc not in (0, 1):
        return AdapterReport(
            scanner="pip-audit",
            available=True,
            skipped_reason=f"pip-audit returned unexpected exit code {rc}",
        )
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return AdapterReport(
            scanner="pip-audit",
            available=True,
            skipped_reason="pip-audit emitted non-JSON output",
        )
    return AdapterReport(
        scanner="pip-audit",
        available=True,
        issues=tuple(_pip_audit_issues(payload)),
    )


def _pip_audit_issues(payload: Any) -> Iterable[SecurityIssue]:
    deps: Iterable[dict[str, Any]]
    if isinstance(payload, dict) and isinstance(payload.get("dependencies"), list):
        deps = payload["dependencies"]
    elif isinstance(payload, list):
        deps = payload
    else:
        return
    for dep in deps:
        name = str(dep.get("name", "")) or "unknown"
        version = str(dep.get("version", "")) or "unknown"
        for vuln in dep.get("vulns", []) or []:
            yield _vuln_issue(
                scanner="pip-audit",
                package=name,
                version=version,
                advisory_id=str(vuln.get("id", "")),
                description=str(vuln.get("description", "")),
                fix_versions=tuple(vuln.get("fix_versions") or ()),
                severity=_severity_from_advisory(str(vuln.get("severity", "") or "")),
            )


def _npm_audit(
    *,
    run: RunCallable,
    cwd: Path,
) -> AdapterReport:
    binary = "npm"
    if not _binary_available(binary):
        return AdapterReport(scanner="npm-audit", available=False, skipped_reason="npm not on PATH")
    lockfiles = [cwd / "package-lock.json", cwd / "npm-shrinkwrap.json"]
    if not any(p.exists() for p in lockfiles):
        return AdapterReport(
            scanner="npm-audit",
            available=False,
            skipped_reason="no package-lock.json / npm-shrinkwrap.json found",
        )
    rc, stdout, _stderr = run([binary, "audit", "--json"], cwd)
    # npm audit returns non-zero when vulns found.
    if rc not in (0, 1):
        return AdapterReport(
            scanner="npm-audit",
            available=True,
            skipped_reason=f"npm audit returned unexpected exit code {rc}",
        )
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return AdapterReport(
            scanner="npm-audit",
            available=True,
            skipped_reason="npm audit emitted non-JSON output",
        )
    return AdapterReport(
        scanner="npm-audit",
        available=True,
        issues=tuple(_npm_audit_issues(payload)),
    )


def _npm_audit_issues(payload: dict[str, Any]) -> Iterable[SecurityIssue]:
    vulns = payload.get("vulnerabilities") or {}
    if not isinstance(vulns, dict):
        return
    for pkg_name, info in vulns.items():
        if not isinstance(info, dict):
            continue
        severity_label = str(info.get("severity", "low"))
        via = info.get("via") or []
        version = str(info.get("range", "unknown"))
        advisory_id = ""
        description = ""
        if isinstance(via, list) and via:
            first = via[0]
            if isinstance(first, dict):
                advisory_id = str(first.get("url") or first.get("source") or "")
                description = str(first.get("title") or "")
        yield _vuln_issue(
            scanner="npm-audit",
            package=str(pkg_name),
            version=version,
            advisory_id=advisory_id,
            description=description,
            fix_versions=(),
            severity=_severity_from_advisory(severity_label),
        )


def _osv_scanner(
    *,
    run: RunCallable,
    cwd: Path,
) -> AdapterReport:
    if not _binary_available("osv-scanner"):
        return AdapterReport(
            scanner="osv-scanner",
            available=False,
            skipped_reason="osv-scanner not on PATH",
        )
    rc, stdout, _stderr = run(["osv-scanner", "--format", "json", "--recursive", "."], cwd)
    if rc not in (0, 1):
        return AdapterReport(
            scanner="osv-scanner",
            available=True,
            skipped_reason=f"osv-scanner returned unexpected exit code {rc}",
        )
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return AdapterReport(
            scanner="osv-scanner",
            available=True,
            skipped_reason="osv-scanner emitted non-JSON output",
        )
    return AdapterReport(
        scanner="osv-scanner",
        available=True,
        issues=tuple(_osv_issues(payload)),
    )


def _osv_issues(payload: dict[str, Any]) -> Iterable[SecurityIssue]:
    results = payload.get("results") or []
    if not isinstance(results, list):
        return
    for result in results:
        if not isinstance(result, dict):
            continue
        for pkg in result.get("packages") or []:
            if not isinstance(pkg, dict):
                continue
            info = pkg.get("package") or {}
            name = str(info.get("name", "unknown"))
            version = str(info.get("version", "unknown"))
            for vuln in pkg.get("vulnerabilities") or []:
                if not isinstance(vuln, dict):
                    continue
                advisory_id = str(vuln.get("id", ""))
                summary = str(vuln.get("summary", ""))
                yield _vuln_issue(
                    scanner="osv-scanner",
                    package=name,
                    version=version,
                    advisory_id=advisory_id,
                    description=summary,
                    fix_versions=(),
                    severity="medium",
                )


# ---------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------


def _severity_from_advisory(label: str) -> str:
    normalized = label.lower().strip()
    if normalized in {"critical"}:
        return "critical"
    if normalized in {"high"}:
        return "high"
    if normalized in {"moderate", "medium"}:
        return "medium"
    if normalized in {"low"}:
        return "low"
    if normalized in {"info", "informational", ""}:
        return "info"
    return "medium"


def _vuln_issue(
    *,
    scanner: str,
    package: str,
    version: str,
    advisory_id: str,
    description: str,
    fix_versions: tuple[str, ...],
    severity: str,
) -> SecurityIssue:
    rule = rule_by_id("SEC-DEPS-VULNERABLE")
    descr = description.strip() or f"{scanner} reported {package} {version} as vulnerable."
    return SecurityIssue(
        rule_id=rule.rule_id,
        severity=severity,  # type: ignore[arg-type]
        confidence=0.95,
        title=f"{package} {version}: {advisory_id or 'vulnerable dependency'}".strip(),
        description=descr,
        route=None,
        evidence={
            "scanner": scanner,
            "package": package,
            "version": version,
            "advisory_id": advisory_id,
            "fix_versions": list(fix_versions),
        },
        recommendation=rule.recommendation,
    )


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------


def run_dependency_scan(
    ctx: CheckContext,
    *,
    project_root: Path,
    run: RunCallable | None = None,
) -> SecurityCheckResult:
    """Drive the configured dependency-scanner adapters.

    ``project_root`` is the directory that contains the lockfile(s);
    in practice it is ``Path.cwd`` for the CLI but tests pin a
    temporary directory.
    """

    run = run or _default_run
    cfg = ctx.config.security.dependency_scanners
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    reports: list[AdapterReport] = []
    if cfg.pip_audit:
        reports.append(_pip_audit(run=run, cwd=project_root))
    if cfg.npm_audit:
        reports.append(_npm_audit(run=run, cwd=project_root))
    if cfg.osv_scanner:
        reports.append(_osv_scanner(run=run, cwd=project_root))
    for report in reports:
        if report.skipped_reason:
            _audit(
                ctx,
                route=None,
                kind="adapter_skip",
                detail=f"scanner={report.scanner} reason={report.skipped_reason}",
            )
            continue
        issues.extend(report.issues)
        _audit(
            ctx,
            route=None,
            kind="adapter_ok",
            detail=f"scanner={report.scanner} issues={len(report.issues)}",
        )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=len(reports),
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _audit(ctx: CheckContext, *, route: str | None, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "route": route or "",
            "detail": detail,
        },
    )


__all__ = [
    "CHECK_NAME",
    "AdapterReport",
    "RunCallable",
    "RunResult",
    "run_dependency_scan",
]
