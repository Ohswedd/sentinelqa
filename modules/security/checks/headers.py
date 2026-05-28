"""Security headers check (Phase 13.02, OWASP Secure Headers Project).

For every route in ``ctx.routes`` we GET the URL once and inspect a
curated set of response headers. Severity mapping follows the OWASP
recommendations referenced in the task spec.

Safety: the check refuses to send any request without a successful
:func:`SafetyPolicy.enforce` decision; the policy is invoked exactly
once per check by the module shell, which also writes one audit-log
entry per probe via :func:`engine.policy.audit_log.write_audit_entry`.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.redaction import redact
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "headers"


def run_headers_check(ctx: CheckContext) -> SecurityCheckResult:
    """Evaluate response headers against the curated rule set."""

    # Defense-in-depth: every entry-point re-enforces the safety policy.
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)

    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        parsed = urlparse(absolute)
        is_https = parsed.scheme == "https"
        try:
            response = ctx.client.get(absolute)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="error", detail=str(exc))
            continue
        targets_scanned += 1
        _audit(
            ctx,
            route=route,
            kind="probe",
            detail=f"status={response.status_code}",
        )
        for issue in _evaluate(route=route, is_https=is_https, headers=response.headers):
            issues.append(issue)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=targets_scanned,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------
# Rule evaluation (pure — easy to unit-test)
# ---------------------------------------------------------------------


def _evaluate(
    *,
    route: str,
    is_https: bool,
    headers: httpx.Headers | dict[str, str],
) -> Iterable[SecurityIssue]:
    name_map = {k.lower(): v for k, v in headers.items()}

    # HSTS — high on HTTPS, skipped on HTTP (browsers ignore HSTS on HTTP).
    if is_https and "strict-transport-security" not in name_map:
        yield _issue("SEC-HEADERS-HSTS-MISSING", severity="high", route=route)

    # CSP — present?
    csp = name_map.get("content-security-policy")
    if csp is None:
        yield _issue("SEC-HEADERS-CSP-MISSING", severity="high", route=route)
    else:
        lowered = csp.lower()
        if "'unsafe-inline'" in lowered or "'unsafe-eval'" in lowered:
            yield _issue(
                "SEC-HEADERS-CSP-UNSAFE-INLINE",
                severity="medium",
                route=route,
                extra={"csp": _redacted(csp)},
            )

    # Clickjacking — XFO or CSP frame-ancestors.
    has_xfo = "x-frame-options" in name_map
    has_frame_ancestors = csp is not None and "frame-ancestors" in csp.lower()
    if not has_xfo and not has_frame_ancestors:
        yield _issue("SEC-HEADERS-XFRAME-MISSING", severity="medium", route=route)

    # XCTO
    if name_map.get("x-content-type-options", "").lower() != "nosniff":
        yield _issue("SEC-HEADERS-XCONTENT-NOSNIFF-MISSING", severity="medium", route=route)

    # Referrer policy
    if "referrer-policy" not in name_map:
        yield _issue("SEC-HEADERS-REFERRER-POLICY-MISSING", severity="low", route=route)

    # Permissions policy (warning only)
    if "permissions-policy" not in name_map:
        yield _issue(
            "SEC-HEADERS-PERMISSIONS-POLICY-MISSING",
            severity="low",
            route=route,
        )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _issue(
    rule_id: str,
    *,
    severity: str,
    route: str,
    extra: dict[str, object] | None = None,
) -> SecurityIssue:
    rule = rule_by_id(rule_id)
    return SecurityIssue(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        confidence=0.95,
        title=rule.title,
        description=rule.description,
        route=route,
        evidence=dict(extra or {}),
        recommendation=rule.recommendation,
    )


def _redacted(value: str) -> str:
    """Run a string through the central redactor (CLAUDE §33)."""

    redacted = redact(value)
    assert isinstance(redacted, str)
    return redacted


def _audit(ctx: CheckContext, *, route: str, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "route": route,
            "detail": detail,
        },
    )


__all__ = ["CHECK_NAME", "run_headers_check"]
