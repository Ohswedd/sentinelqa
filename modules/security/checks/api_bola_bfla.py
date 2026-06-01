"""OWASP API Top-10 BOLA / BFLA replay.

Replays observed API calls captured under identity **A** (the primary
``auth`` config) under identity **B** (``auth.second_user``). Two
outcomes are findings:

- **BOLA** (Broken Object-Level Authorization, OWASP API-2023-01):
 endpoint returns 200 with payload that references A's data when
 called as B.
- **BFLA** (Broken Function-Level Authorization, OWASP API-2023-03):
 an admin-shaped endpoint returns 2xx when called as a non-admin
 identity.

The probe is hard-gated behind ``security.mode == 'authorized_destructive'``,
a non-empty ``target.proof_of_authorization``, and a hard endpoint cap
(``max_endpoints``, default 50). our engineering rules: no payload mutation,
no escape-attempt logic, no detection-evasion code path.
"""

from __future__ import annotations

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

CHECK_NAME = "api_bola_bfla"

_DEFAULT_MAX_ENDPOINTS: Final[int] = 50
_ADMIN_PATH_TOKENS: Final[tuple[str, ...]] = (
    "/admin",
    "/manage",
    "/internal",
    "/super",
)


@dataclass(frozen=True, slots=True)
class CapturedCall:
    """A single observed API call captured under identity A."""

    method: str
    url: str
    body_shape: tuple[str, ...]
    """Sorted tuple of top-level JSON keys observed in A's response body."""


@dataclass(frozen=True, slots=True)
class ReplayHeaders:
    """Auth headers to replay calls under another identity."""

    identity_a: dict[str, str]
    identity_b: dict[str, str]
    b_is_admin: bool = False


def _ensure_gated(ctx: CheckContext) -> None:
    if ctx.safety.mode != "authorized_destructive":
        raise ConfigError("api_bola_bfla requires security.mode='authorized_destructive'.")
    if not ctx.target.proof_of_authorization:
        raise ConfigError("api_bola_bfla requires target.proof_of_authorization.")


def _looks_admin_path(url: str) -> bool:
    lower = url.lower()
    return any(token in lower for token in _ADMIN_PATH_TOKENS)


def classify_replay(
    captured: CapturedCall,
    replay_status: int,
    replay_body: Any,
    *,
    b_is_admin: bool,
) -> Literal["clean", "bola", "bfla"] | None:
    """Decide whether a replay is BOLA, BFLA, or clean.

    Returns ``None`` for a malformed input. Pure function — unit tests
    exercise the classifier directly without HTTP I/O.
    """

    if not 200 <= replay_status < 300:
        return "clean"
    # BFLA: admin-shaped path + non-admin replay identity gets 2xx.
    if _looks_admin_path(captured.url) and not b_is_admin:
        return "bfla"
    # BOLA: response body shape matches the captured A response shape AND
    # the URL contains a path id segment.
    if isinstance(replay_body, dict):
        body_shape = tuple(sorted(replay_body.keys()))
        if body_shape == captured.body_shape and _has_path_id(captured.url):
            return "bola"
    return "clean"


def _has_path_id(url: str) -> bool:
    # Crude heuristic: a path segment that's numeric or UUID-shaped.
    import re

    return re.search(r"/(\d+|[0-9a-f-]{8,})(/|$)", url) is not None


def replay_call(
    client: httpx.Client,
    captured: CapturedCall,
    headers: ReplayHeaders,
) -> tuple[int, Any]:
    response = client.request(
        captured.method,
        captured.url,
        headers=headers.identity_b,
        timeout=10.0,
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def evaluate_classification(
    captured: CapturedCall,
    classification: str,
) -> Iterable[SecurityIssue]:
    if classification == "bola":
        yield SecurityIssue(
            rule_id="SEC-BOLA-CROSS-TENANT-READ",
            severity="critical",
            confidence=0.95,
            title=f"BOLA: {captured.method} {captured.url} exposed across identities",
            description=(
                "Endpoint returned identity-A's response shape when called "
                "as identity B. Object-level authorization is missing. "
                "CWE-639 / OWASP API-2023-01."
            ),
            route=captured.url,
            evidence={
                "method": captured.method,
                "url": captured.url,
                "body_shape": ",".join(captured.body_shape),
                "cwe_id": "CWE-639",
                "owasp_api_id": "API-2023-01",
            },
            recommendation=(
                "Enforce object ownership server-side; require the "
                "caller's identity to match the resource owner."
            ),
        )
    elif classification == "bfla":
        yield SecurityIssue(
            rule_id="SEC-BFLA-ELEVATED-ACTION",
            severity="high",
            confidence=0.95,
            title=f"BFLA: {captured.method} {captured.url} accepts non-admin identity",
            description=(
                "Admin-shaped endpoint returned 2xx when called as a "
                "non-admin identity. CWE-863 / OWASP API-2023-03."
            ),
            route=captured.url,
            evidence={
                "method": captured.method,
                "url": captured.url,
                "cwe_id": "CWE-863",
                "owasp_api_id": "API-2023-03",
            },
            recommendation=(
                "Enforce role-based authorization before the controller "
                "body runs; deny by default."
            ),
        )


def run_bola_bfla_check(
    ctx: CheckContext,
    *,
    captured_calls: Sequence[CapturedCall],
    headers: ReplayHeaders,
    max_endpoints: int = _DEFAULT_MAX_ENDPOINTS,
) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    _ensure_gated(ctx)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    scanned = 0
    for captured in captured_calls[:max_endpoints]:
        scanned += 1
        try:
            status, body = replay_call(ctx.client, captured, headers)
        except httpx.HTTPError as exc:
            _audit(
                ctx,
                kind="error",
                detail=f"{captured.method} {captured.url}: {exc}",
            )
            continue
        classification = classify_replay(captured, status, body, b_is_admin=headers.b_is_admin)
        if classification in {"bola", "bfla"}:
            issues.extend(evaluate_classification(captured, classification))
        _audit(
            ctx,
            kind="probe",
            detail=(f"{captured.method} {captured.url} -> {status} " f"({classification})"),
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
    "CapturedCall",
    "ReplayHeaders",
    "classify_replay",
    "evaluate_classification",
    "replay_call",
    "run_bola_bfla_check",
]
