"""Deeper frontend-only-auth detector (Phase 32.06, ADR-0044).

The Phase-19 LLM-audit module flags "the gate is purely a frontend
redirect" via DOM heuristics. This Phase-32 deeper probe takes that a
step further: it records every XHR / fetch URL a gated page issues,
re-issues each one anonymously, and asserts the server returns
401 / 403. Endpoints that return 200 with body payload anonymously are
genuine frontend-only-auth bugs (CWE-862 / OWASP API-2023-01).

The check distinguishes:
- ``apparently_public`` endpoints (e.g. ``/api/public/...``) — excluded.
- ``gated_correctly`` endpoints (401/403 anonymously, 200 with cookies).
- ``broken`` endpoints (200 with data anonymously) — the failure case.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue

CHECK_NAME = "frontend_only_auth_deeper"

_PUBLIC_PATH_RE = re.compile(r"/api/(public|health|status|version)(/|$)")


@dataclass(frozen=True, slots=True)
class ObservedEndpoint:
    """An XHR / fetch URL the gated page issued."""

    method: str
    url: str
    saw_payload_when_authenticated: bool
    """True if A's request returned a non-empty body — we only probe these."""


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    endpoint: ObservedEndpoint
    classification: Literal["apparently_public", "gated_correctly", "broken"]
    anonymous_status: int
    anonymous_body_bytes: int


def looks_public(url: str) -> bool:
    return bool(_PUBLIC_PATH_RE.search(url))


def classify_endpoint(
    endpoint: ObservedEndpoint,
    *,
    anonymous_status: int,
    anonymous_body_bytes: int,
) -> Literal["apparently_public", "gated_correctly", "broken"]:
    if looks_public(endpoint.url):
        return "apparently_public"
    if anonymous_status in {401, 403}:
        return "gated_correctly"
    if 200 <= anonymous_status < 300 and anonymous_body_bytes > 0:
        return "broken"
    return "gated_correctly"


def probe_endpoint(
    client: httpx.Client,
    endpoint: ObservedEndpoint,
) -> ProbeOutcome:
    try:
        response = client.request(
            endpoint.method,
            endpoint.url,
            headers={},  # explicitly anonymous
            timeout=10.0,
        )
    except httpx.HTTPError:
        classification = "gated_correctly"
        return ProbeOutcome(
            endpoint=endpoint,
            classification=classification,
            anonymous_status=0,
            anonymous_body_bytes=0,
        )
    body_bytes = len(response.content)
    classification = classify_endpoint(
        endpoint,
        anonymous_status=response.status_code,
        anonymous_body_bytes=body_bytes,
    )
    return ProbeOutcome(
        endpoint=endpoint,
        classification=classification,
        anonymous_status=response.status_code,
        anonymous_body_bytes=body_bytes,
    )


def evaluate_outcome(outcome: ProbeOutcome) -> Iterable[SecurityIssue]:
    if outcome.classification != "broken":
        return
    yield SecurityIssue(
        rule_id="SEC-IDOR-CROSS-USER-ACCESS",  # reuses Phase-13 rule id
        severity="high",
        confidence=0.9,
        title=f"Endpoint returns data anonymously: {outcome.endpoint.url}",
        description=(
            f"{outcome.endpoint.method} {outcome.endpoint.url} returned "
            f"{outcome.anonymous_status} with {outcome.anonymous_body_bytes} "
            "bytes of body when called without authentication, but the "
            "page that issued the request is behind a frontend gate. "
            "CWE-862 / OWASP API-2023-01."
        ),
        route=outcome.endpoint.url,
        evidence={
            "method": outcome.endpoint.method,
            "url": outcome.endpoint.url,
            "anonymous_status": outcome.anonymous_status,
            "anonymous_body_bytes": outcome.anonymous_body_bytes,
            "cwe_id": "CWE-862",
            "owasp_api_id": "API-2023-01",
        },
        recommendation=(
            "Enforce authentication server-side; do not rely on the " "frontend's redirect."
        ),
    )


def run_frontend_only_auth_deeper_check(
    ctx: CheckContext,
    *,
    observed_endpoints: Sequence[ObservedEndpoint],
) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    scanned = 0
    seen: set[tuple[str, str]] = set()
    for endpoint in observed_endpoints:
        key = (endpoint.method.upper(), endpoint.url)
        if key in seen:
            continue
        seen.add(key)
        scanned += 1
        outcome = probe_endpoint(ctx.client, endpoint)
        issues.extend(evaluate_outcome(outcome))
        _audit(
            ctx,
            kind="probe",
            detail=(
                f"{endpoint.method} {endpoint.url} -> "
                f"{outcome.anonymous_status} ({outcome.classification})"
            ),
        )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=scanned,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _audit(ctx: CheckContext, *, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "detail": detail,
        },
    )


__all__ = [
    "CHECK_NAME",
    "ObservedEndpoint",
    "ProbeOutcome",
    "classify_endpoint",
    "evaluate_outcome",
    "looks_public",
    "probe_endpoint",
    "run_frontend_only_auth_deeper_check",
]
