"""Safe SQLi probe (Phase 13.06).

OFF by default. Enabled only when:

- ``config.security.checks.sqli == True`` AND
- ``target.mode == "local"`` (i.e. host is loopback / RFC1918), OR
- ``security.mode == "authorized_destructive"`` with a valid proof-of-
  authorization document.

The probe technique is **behavioural, not exploitative**:

- Send ``true`` and ``false`` boolean payloads (`' OR '1'='1` vs
  `' AND '1'='2`).
- Send one short time-based payload, capped at a 2-second pg_sleep
  equivalent so we cannot exhaust resources.
- Compare status code + body length + elapsed time across the
  baseline, true, and false probes. A statistically clear divergence
  raises a critical finding.

We do NOT extract data, NOT enumerate database schema, NOT chain into
a follow-up payload. Confirmation requires manual review.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from engine.errors.base import ConfigError, DestructiveWithoutProofError
from engine.policy.audit_log import write_audit_entry
from engine.policy.proof_of_authorization import require_proof
from engine.policy.safety import SafetyPolicy, is_local

from modules.security.checks.context import CheckContext
from modules.security.http_client import TokenBucket
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "sqli"

PAYLOADS_TRUE = ("' OR '1'='1", "1 OR 1=1 -- ")
PAYLOADS_FALSE = ("' AND '1'='2", "1 AND 1=0 -- ")
PAYLOADS_TIME = ("'; SELECT pg_sleep(2)-- ",)  # capped

BODY_DELTA_THRESHOLD = 200  # absolute char delta
TIME_DELTA_THRESHOLD_MS = 1500


def _allowed_to_run(ctx: CheckContext) -> tuple[bool, str]:
    if not ctx.config.security.checks.sqli:
        return False, "config.security.checks.sqli is false"
    if is_local(ctx.safety.host):
        return True, "local target"
    if ctx.config.security.mode != "authorized_destructive":
        return False, "non-local target requires security.mode='authorized_destructive'"
    if ctx.target.proof_of_authorization is None:
        return False, "no proof-of-authorization document configured"
    try:
        require_proof(
            ctx.target.proof_of_authorization,
            host=ctx.safety.host,
            capability="destructive",
        )
    except DestructiveWithoutProofError as exc:
        return False, str(exc)
    except ConfigError as exc:
        return False, f"proof-of-authorization unreadable: {exc}"
    return True, ""


@dataclass(frozen=True, slots=True)
class _ProbeReading:
    status: int
    body_len: int
    elapsed_ms: int


def _probe(
    client: httpx.Client,
    absolute: str,
    bucket: TokenBucket,
) -> _ProbeReading | None:
    bucket.take()
    start = time.monotonic()
    try:
        response = client.get(absolute)
    except httpx.HTTPError:
        return None
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return _ProbeReading(
        status=response.status_code,
        body_len=len(response.text or ""),
        elapsed_ms=elapsed_ms,
    )


def _inject_into_query(absolute: str, payload: str) -> tuple[str, list[str]] | None:
    parsed = urlparse(absolute)
    params = parse_qsl(parsed.query, keep_blank_values=True)
    if not params:
        return None
    injected = [(name, payload) for name, _ in params]
    new = urlunparse(parsed._replace(query=urlencode(injected, doseq=False)))
    return new, [n for n, _ in params]


def run_sqli_check(ctx: CheckContext) -> SecurityCheckResult:
    ok, reason = _allowed_to_run(ctx)
    if not ok:
        _audit(ctx, route="*", kind="skipped", detail=reason)
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=0,
            skipped=True,
            skipped_reason=reason,
        )

    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    bucket = TokenBucket(rate_per_second=float(ctx.config.security.max_requests_per_second))

    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        baseline = _probe(ctx.client, absolute, bucket)
        if baseline is None:
            _audit(ctx, route=route, kind="error", detail="baseline_failed")
            continue
        targets_scanned += 1
        _audit(ctx, route=route, kind="baseline", detail=f"status={baseline.status}")

        true_url_pair = _inject_into_query(absolute, PAYLOADS_TRUE[0])
        false_url_pair = _inject_into_query(absolute, PAYLOADS_FALSE[0])
        time_url_pair = _inject_into_query(absolute, PAYLOADS_TIME[0])
        if true_url_pair is None or false_url_pair is None:
            # No query string to inject — skip silently (no false positive).
            continue
        true_url, params = true_url_pair
        false_url, _ = false_url_pair
        true_reading = _probe(ctx.client, true_url, bucket)
        false_reading = _probe(ctx.client, false_url, bucket)
        time_reading = (
            _probe(ctx.client, time_url_pair[0], bucket) if time_url_pair is not None else None
        )
        if true_reading is None or false_reading is None:
            continue

        body_delta = abs(true_reading.body_len - false_reading.body_len)
        status_changed = true_reading.status != false_reading.status
        time_delta = 0
        if time_reading is not None:
            time_delta = max(0, time_reading.elapsed_ms - baseline.elapsed_ms)

        suspicious = (
            body_delta >= BODY_DELTA_THRESHOLD
            or status_changed
            or time_delta >= TIME_DELTA_THRESHOLD_MS
        )
        if suspicious:
            issues.append(
                _issue(
                    "SEC-SQLI-BEHAVIORAL",
                    severity="critical",
                    route=route,
                    extra={
                        "probed_params": params,
                        "baseline_status": baseline.status,
                        "true_status": true_reading.status,
                        "false_status": false_reading.status,
                        "body_delta": body_delta,
                        "time_delta_ms": time_delta,
                    },
                )
            )
        _audit(
            ctx,
            route=route,
            kind="probe",
            detail=(
                f"body_delta={body_delta} status_changed={status_changed} "
                f"time_delta_ms={time_delta}"
            ),
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
        confidence=0.75,
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


__all__ = [
    "CHECK_NAME",
    "BODY_DELTA_THRESHOLD",
    "TIME_DELTA_THRESHOLD_MS",
    "PAYLOADS_TRUE",
    "PAYLOADS_FALSE",
    "PAYLOADS_TIME",
    "run_sqli_check",
]
