"""CORS misconfiguration check.

For each route in ``ctx.routes`` we send an ``OPTIONS`` preflight from
a synthetic ``Origin`` (``https://sentinelqa.invalid``). We then read
``Access-Control-Allow-Origin`` (ACAO) and
``Access-Control-Allow-Credentials`` (ACAC):

- ACAO=``*`` + ACAC=``true`` → critical (modern browsers ignore the
 combination, but the server announcing it indicates a misconfig).
- ACAO echoes our synthetic origin → high (reflective).

The synthetic origin is a non-routable invalid TLD so the probe never
leaks real third-party hostnames.
"""

from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "cors"
SYNTHETIC_ORIGIN = "https://sentinelqa.invalid"


def run_cors_check(ctx: CheckContext) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        try:
            response = ctx.client.request(
                "OPTIONS",
                absolute,
                headers={
                    "Origin": SYNTHETIC_ORIGIN,
                    "Access-Control-Request-Method": "GET",
                },
            )
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="error", detail=str(exc))
            continue
        targets_scanned += 1
        _audit(ctx, route=route, kind="probe", detail=f"status={response.status_code}")
        acao = response.headers.get("access-control-allow-origin")
        acac = response.headers.get("access-control-allow-credentials", "").lower() == "true"
        if acao is None:
            continue
        is_wildcard = acao.strip() == "*"
        is_reflective = acao.strip().lower() == SYNTHETIC_ORIGIN.lower()
        if is_wildcard and acac:
            issues.append(
                _issue(
                    "SEC-CORS-WILDCARD-CREDENTIALS",
                    severity="critical",
                    route=route,
                    extra={"acao": acao, "allow_credentials": True},
                )
            )
        if is_reflective:
            issues.append(
                _issue(
                    "SEC-CORS-REFLECTIVE-ALLOW-ORIGIN",
                    severity="high",
                    route=route,
                    extra={"reflected_origin": SYNTHETIC_ORIGIN},
                )
            )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=targets_scanned,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _issue(rule_id: str, *, severity: str, route: str, extra: dict[str, object]) -> SecurityIssue:
    rule = rule_by_id(rule_id)
    return SecurityIssue(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        confidence=0.9,
        title=rule.title,
        description=rule.description,
        route=route,
        evidence=dict(extra),
        recommendation=rule.recommendation,
    )


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


__all__ = ["CHECK_NAME", "SYNTHETIC_ORIGIN", "run_cors_check"]
