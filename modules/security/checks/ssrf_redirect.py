"""SSRF / open-redirect surface mapper (Phase 32.08, ADR-0044).

For each URL-shaped form field / query parameter the discovery module
surfaces, send a small *fixed* list of canonical "internal target"
payloads (loopback, AWS metadata, file://, redis gopher), and a
canonical pair of open-redirect bait URLs. Flag responses that
suggest the server followed the URL (any non-rejection) or that
emitted a 30x with the attacker domain in `Location`.

our engineering rules: the payload list is a fixed, enumerated set. No
randomised input, no payload mutation, no permutation generator. Hard-gated
behind ``security.mode == 'authorized_destructive'`` AND a non-empty
``target.proof_of_authorization`` (re-uses the same gate as
:mod:`modules.security.checks.api_bola_bfla`).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import httpx
from engine.errors.base import ConfigError
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue

CHECK_NAME = "ssrf_redirect"

SSRF_PAYLOADS: Final[tuple[str, ...]] = (
    "http://127.0.0.1/",
    "http://localhost/",
    "http://169.254.169.254/",
    "http://[::1]/",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_PING%0a",
)

OPEN_REDIRECT_PAYLOADS: Final[tuple[str, ...]] = (
    "//attacker.example.com",
    "https://attacker.example.com.legit.com.allowedhost.example",
)

_REJECTION_HINTS: Final[tuple[str, ...]] = (
    "could not resolve",
    "invalid url",
    "blocked",
    "forbidden host",
    "not allowed",
    "ssrf",
)


@dataclass(frozen=True, slots=True)
class UrlInput:
    """A discovered URL-shaped input."""

    method: str
    url: str
    parameter: str
    """The name of the field/param that takes a URL value."""


@dataclass(frozen=True, slots=True)
class SsrfProbeOutcome:
    input: UrlInput
    payload: str
    status: int
    body_excerpt: str
    classification: Literal["clean", "ssrf_suspected"]


@dataclass(frozen=True, slots=True)
class RedirectProbeOutcome:
    input: UrlInput
    payload: str
    status: int
    location: str | None
    classification: Literal["clean", "open_redirect"]


def _ensure_gated(ctx: CheckContext) -> None:
    if ctx.safety.mode != "authorized_destructive":
        raise ConfigError("ssrf_redirect requires security.mode='authorized_destructive'.")
    if not ctx.target.proof_of_authorization:
        raise ConfigError("ssrf_redirect requires target.proof_of_authorization.")


def _body_excerpt(body: bytes) -> str:
    text = body[:200].decode("utf-8", errors="replace")
    # Strip control characters for safe logging.
    return re.sub(r"[\x00-\x1f]+", " ", text)


def classify_ssrf_response(status: int, body: bytes) -> Literal["clean", "ssrf_suspected"]:
    if 400 <= status < 500:
        return "clean"
    lower = body[:512].decode("utf-8", errors="replace").lower()
    if any(hint in lower for hint in _REJECTION_HINTS):
        return "clean"
    return "ssrf_suspected"


def classify_redirect_response(
    status: int, location: str | None
) -> Literal["clean", "open_redirect"]:
    if location is None:
        return "clean"
    if 300 <= status < 400 and any(bad in location for bad in OPEN_REDIRECT_PAYLOADS):
        return "open_redirect"
    return "clean"


def evaluate_ssrf(outcome: SsrfProbeOutcome) -> Iterable[SecurityIssue]:
    if outcome.classification != "ssrf_suspected":
        return
    yield SecurityIssue(
        rule_id="SEC-SSRF-SUSPECTED",
        severity="high",
        confidence=0.85,
        title=(
            f"SSRF suspected: {outcome.input.method} "
            f"{outcome.input.url} (param={outcome.input.parameter})"
        ),
        description=(
            "The server returned a non-rejection response when fed "
            f"`{outcome.payload}` into the URL-shaped input. CWE-918."
        ),
        route=outcome.input.url,
        evidence={
            "method": outcome.input.method,
            "url": outcome.input.url,
            "parameter": outcome.input.parameter,
            "payload": outcome.payload,
            "status": outcome.status,
            "body_excerpt": outcome.body_excerpt,
            "cwe_id": "CWE-918",
            "owasp_api_id": "API-2023-07",
        },
        recommendation=(
            "Validate that user-supplied URLs resolve outside the "
            "server's local network; deny loopback, link-local, "
            "private CIDRs, and all non-HTTP schemes."
        ),
    )


def evaluate_redirect(outcome: RedirectProbeOutcome) -> Iterable[SecurityIssue]:
    if outcome.classification != "open_redirect":
        return
    yield SecurityIssue(
        rule_id="SEC-OPEN-REDIRECT",
        severity="medium",
        confidence=0.95,
        title=(
            f"Open redirect: {outcome.input.method} "
            f"{outcome.input.url} (param={outcome.input.parameter})"
        ),
        description=(
            f"Redirect endpoint emitted a {outcome.status} with "
            f"`{outcome.location}` in `Location` when fed "
            f"`{outcome.payload}`. CWE-601."
        ),
        route=outcome.input.url,
        evidence={
            "method": outcome.input.method,
            "url": outcome.input.url,
            "parameter": outcome.input.parameter,
            "payload": outcome.payload,
            "status": outcome.status,
            "location": outcome.location,
            "cwe_id": "CWE-601",
        },
        recommendation=(
            "Restrict redirect destinations to an allowlist of known " "callback URLs."
        ),
    )


def _send_payload(
    client: httpx.Client,
    input_: UrlInput,
    payload: str,
) -> tuple[int, bytes, str | None]:
    if input_.method.upper() == "GET":
        response = client.get(
            input_.url,
            params={input_.parameter: payload},
            timeout=10.0,
            follow_redirects=False,
        )
    else:
        response = client.request(
            input_.method,
            input_.url,
            json={input_.parameter: payload},
            timeout=10.0,
            follow_redirects=False,
        )
    return response.status_code, response.content, response.headers.get("location")


def run_ssrf_redirect_check(
    ctx: CheckContext,
    *,
    inputs: Sequence[UrlInput],
) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    _ensure_gated(ctx)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    scanned = 0
    for input_ in inputs:
        for payload in SSRF_PAYLOADS:
            try:
                status, body, _location = _send_payload(ctx.client, input_, payload)
            except httpx.HTTPError as exc:
                _audit(ctx, kind="error", detail=f"{input_.url}: {exc}")
                continue
            outcome = SsrfProbeOutcome(
                input=input_,
                payload=payload,
                status=status,
                body_excerpt=_body_excerpt(body),
                classification=classify_ssrf_response(status, body),
            )
            issues.extend(evaluate_ssrf(outcome))
        for payload in OPEN_REDIRECT_PAYLOADS:
            try:
                status, _body, location = _send_payload(ctx.client, input_, payload)
            except httpx.HTTPError as exc:
                _audit(ctx, kind="error", detail=f"{input_.url}: {exc}")
                continue
            r_outcome = RedirectProbeOutcome(
                input=input_,
                payload=payload,
                status=status,
                location=location,
                classification=classify_redirect_response(status, location),
            )
            issues.extend(evaluate_redirect(r_outcome))
        scanned += 1
    elapsed_ms = int((time.monotonic() - start) * 1000)
    _audit(
        ctx,
        kind="complete",
        detail=f"inputs={scanned} issues={len(issues)}",
    )
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


# Keep `Any` imported (used implicitly via _send_payload defaults)
_: Any = None


__all__ = [
    "CHECK_NAME",
    "OPEN_REDIRECT_PAYLOADS",
    "RedirectProbeOutcome",
    "SSRF_PAYLOADS",
    "SsrfProbeOutcome",
    "UrlInput",
    "classify_redirect_response",
    "classify_ssrf_response",
    "evaluate_redirect",
    "evaluate_ssrf",
    "run_ssrf_redirect_check",
]
