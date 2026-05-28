"""Reflected-XSS safe probe (Phase 13.05).

The probe inserts a unique non-executable marker into each query
parameter of the route URL and looks for the marker reflected
*unescaped* in the response body. The marker payload
(``<svg/onload=__SENTINELQA_XSS__>``) contains the literal substring
``__SENTINELQA_XSS__`` which is what we grep for — finding it
*together with* the literal ``<svg`` opening tag (or ``onload=``)
indicates the value was injected raw into HTML.

Safety contract (CLAUDE §6/§26):

- Every probe is rate-limited by ``security.max_requests_per_second``.
- ``SafetyPolicy.enforce`` is called once before the first probe.
- One audit-log entry per probe is appended via
  :func:`engine.policy.audit_log.write_audit_entry`.
- The probe never bypasses CAPTCHAs, evades WAFs, or changes the User-
  Agent. It looks like SentinelQA on the wire.
- We do NOT enumerate routes outside ``ctx.routes``; the caller is
  responsible for keeping the route set scoped to authorized targets.
"""

from __future__ import annotations

import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.http_client import TokenBucket
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "xss_reflected"

MARKER = "__SENTINELQA_XSS__"
PAYLOAD = f"<svg/onload={MARKER}>"


def _build_probed_url(absolute: str, payload: str) -> tuple[str, list[str]]:
    """Return ``(probed_url, probed_param_names)`` for one route.

    If the URL has no query params, we inject a single ``q=`` parameter.
    Otherwise we replace every existing parameter's value with the marker
    payload. We never strip params — fidelity matters for reflection
    detection.
    """

    parsed = urlparse(absolute)
    params = parse_qsl(parsed.query, keep_blank_values=True)
    if not params:
        params = [("q", payload)]
        names = ["q"]
    else:
        params = [(name, payload) for name, _ in params]
        names = [name for name, _ in params]
    new_query = urlencode(params, doseq=False)
    return urlunparse(parsed._replace(query=new_query)), names


def _has_reflection(body: str, marker: str = MARKER) -> bool:
    if marker not in body:
        return False
    # The marker also has to live inside an HTML-like tag context. If it
    # appears inside an HTML-escaped string (``&lt;svg/onload=...``) the
    # browser will NOT execute it; we treat that as escaped (no finding).
    return ("<svg" in body or "onload=" in body) and "&lt;svg" not in body


def run_xss_reflected_check(ctx: CheckContext) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    rate = ctx.config.security.max_requests_per_second
    bucket = TokenBucket(rate_per_second=float(rate))
    csp_lowered = ""

    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        probed, param_names = _build_probed_url(absolute, PAYLOAD)
        bucket.take()
        try:
            response = ctx.client.get(probed)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="error", detail=str(exc))
            continue
        targets_scanned += 1
        _audit(
            ctx,
            route=route,
            kind="probe",
            detail=(
                f"status={response.status_code} params={','.join(param_names)} " "payload=marker"
            ),
        )
        # CSP reduces confidence (XSS would be mitigated even if reflected).
        csp = response.headers.get("content-security-policy", "")
        csp_lowered = csp.lower()
        body = response.text or ""
        if _has_reflection(body):
            confidence = 0.6 if ("script-src" in csp_lowered and "'self'" in csp_lowered) else 0.9
            issues.append(
                _issue(
                    "SEC-XSS-REFLECTED",
                    severity="high",
                    route=route,
                    confidence=confidence,
                    extra={
                        "probed_url": probed,
                        "probed_params": param_names,
                        "marker": MARKER,
                        "csp_present": bool(csp),
                    },
                )
            )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=targets_scanned,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _issue(
    rule_id: str,
    *,
    severity: str,
    route: str,
    confidence: float,
    extra: dict[str, object],
) -> SecurityIssue:
    rule = rule_by_id(rule_id)
    return SecurityIssue(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        confidence=confidence,
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


__all__ = ["CHECK_NAME", "MARKER", "PAYLOAD", "run_xss_reflected_check"]
