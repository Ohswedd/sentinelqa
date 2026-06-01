"""SAST adapter.

OFF by default. Enable via:

 security:
 checks:
 sast: true
 dependency_scanners:
 semgrep: true

Adapter is a thin subprocess wrapper around ``semgrep --config auto
--json``. Outputs are normalized into :class:`SecurityIssue` records
under the ``SEC-SAST-FINDING`` rule.

Like the dep-scanner adapters, the binary's absence is reported via
``skipped_reason`` so the operator can install semgrep deliberately
(``CLAUDE §35``: dependencies must justify themselves; semgrep is
heavy, so we never auto-install).
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from engine.policy.audit_log import write_audit_entry

from modules.security.checks.context import CheckContext
from modules.security.checks.deps import RunCallable, _default_run
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "sast"


def _semgrep_available() -> bool:
    return shutil.which("semgrep") is not None


def run_sast(
    ctx: CheckContext,
    *,
    project_root: Path,
    run: RunCallable | None = None,
) -> SecurityCheckResult:
    """Run semgrep and translate findings."""

    run = run or _default_run
    if not ctx.config.security.dependency_scanners.semgrep:
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=0,
            skipped=True,
            skipped_reason="security.dependency_scanners.semgrep is false",
        )
    if not _semgrep_available():
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=0,
            skipped=True,
            skipped_reason="semgrep not on PATH",
        )
    start = time.monotonic()
    rc, stdout, stderr = run(
        ["semgrep", "--config", "auto", "--json", "--quiet", str(project_root)],
        project_root,
    )
    if rc not in (0, 1):
        _audit(
            ctx,
            kind="adapter_error",
            detail=f"semgrep exit={rc} stderr={stderr[:200]!r}",
        )
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=int((time.monotonic() - start) * 1000),
            skipped=True,
            skipped_reason=f"semgrep returned unexpected exit code {rc}",
        )
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=int((time.monotonic() - start) * 1000),
            skipped=True,
            skipped_reason="semgrep emitted non-JSON output",
        )
    issues = tuple(_semgrep_issues(payload))
    _audit(ctx, kind="adapter_ok", detail=f"findings={len(issues)}")
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=1,
        issues=issues,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


def _semgrep_issues(payload: dict[str, Any]) -> Iterable[SecurityIssue]:
    results = payload.get("results") or []
    if not isinstance(results, list):
        return
    rule = rule_by_id("SEC-SAST-FINDING")
    for result in results:
        if not isinstance(result, dict):
            continue
        check_id = str(result.get("check_id", ""))
        path = str(result.get("path", ""))
        line = int(result.get("start", {}).get("line", 0) or 0)
        extra = result.get("extra") or {}
        message = str(extra.get("message", "")) or "Semgrep rule matched."
        severity_label = str(extra.get("severity", "INFO")).lower()
        severity = _severity_from_semgrep(severity_label)
        yield SecurityIssue(
            rule_id=rule.rule_id,
            severity=severity,  # type: ignore[arg-type]
            confidence=0.7,
            title=f"semgrep {check_id}".strip(),
            description=message,
            route=None,
            evidence={
                "tool": "semgrep",
                "check_id": check_id,
                "path": path,
                "line": line,
            },
            recommendation=rule.recommendation,
        )


def _severity_from_semgrep(value: str) -> str:
    normalized = value.lower().strip()
    if normalized in {"error", "critical"}:
        return "high"
    if normalized in {"warning"}:
        return "medium"
    return "low"


def _audit(ctx: CheckContext, *, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "route": "",
            "detail": detail,
        },
    )


__all__ = ["CHECK_NAME", "run_sast"]
