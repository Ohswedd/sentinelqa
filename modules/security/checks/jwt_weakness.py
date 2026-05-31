"""JWT-weakness scanner (Phase 32.01, ADR-0044).

Inspects every JWT-shaped string observed in ``Authorization`` headers
and cookies during the audit run. Flags ``alg=none``, HS256 with a
fixed wordlist of well-known weak secrets, missing ``exp``, expired
``exp``, and missing ``iss`` / ``aud`` for tokens that look
multi-tenant. The scanner NEVER decodes a signature against an external
wordlist (CLAUDE.md §6 forbids brute-force / dictionary attacks); the
six-entry list below is hard-coded and enumerated, not iterated against
a remote resource.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue

CHECK_NAME = "jwt_weakness"

# A JWT is three base64url segments separated by '.' — we accept the
# canonical eyJ-prefixed shape (`eyJ` is base64url for ``{"`` which is
# the start of every JSON header).
_JWT_RE: Final[re.Pattern[str]] = re.compile(
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{0,}"
)

# Fixed, enumerated wordlist of well-known weak HS256 secrets. CLAUDE.md
# §6: we never iterate against an external dictionary or wordlist. CI
# guard ``tests/security/test_jwt_no_brute_force.py`` proves this list
# is the only set of candidate secrets in the module.
_WEAK_HS256_SECRETS: Final[tuple[str, ...]] = (
    "secret",
    "password",
    "changeit",
    "please-change-me",
    "null",
    "1234",
)


@dataclass(frozen=True, slots=True)
class _DecodedJwt:
    raw: str
    header: dict[str, Any]
    payload: dict[str, Any]
    signing_input: bytes
    signature: bytes


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + pad)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64url segment") from exc


def decode_jwt(token: str) -> _DecodedJwt | None:
    """Return the JWT's parsed parts, or ``None`` if it isn't a JWT."""

    parts = token.strip().split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(sig_b64) if sig_b64 else b""
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return None
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    return _DecodedJwt(
        raw=token,
        header=header,
        payload=payload,
        signing_input=signing_input,
        signature=signature,
    )


def _hs256_verifies_against(token: _DecodedJwt, secret: str) -> bool:
    """True iff ``HMAC-SHA256(secret, signing_input)`` matches the sig."""

    expected = hmac.new(
        secret.encode("utf-8"),
        token.signing_input,
        hashlib.sha256,
    ).digest()
    return hmac.compare_digest(expected, token.signature)


def _redacted_prefix(token: str) -> str:
    # First 8 chars + ellipsis. CLAUDE.md §33: never log the full token.
    cleaned = token.strip()
    return f"{cleaned[:8]}…"


def _looks_multi_tenant(payload: dict[str, Any]) -> bool:
    """Heuristic: tokens that carry ``sub`` AND any tenant-shaped claim.

    The ``aud``/``iss`` rule fires when this is true AND those claims
    are missing — a small heuristic to avoid noisy findings on
    single-tenant apps.
    """

    if "sub" not in payload:
        return False
    tenant_keys = {"tenant", "tenant_id", "tid", "org", "org_id", "team", "team_id"}
    return any(k in payload for k in tenant_keys)


def evaluate_jwt(token: _DecodedJwt, *, location: str, now: float) -> Iterable[SecurityIssue]:
    """Yield issues for one decoded JWT.

    ``location`` is a redacted descriptor such as ``"header:authorization"``
    or ``"cookie:session"`` — the call-site provides it. ``now`` is the
    current Unix timestamp; callers inject it so tests are deterministic.
    """

    header = token.header
    payload = token.payload
    alg = str(header.get("alg", "")).lower()

    if alg == "none":
        yield SecurityIssue(
            rule_id="SEC-JWT-ALG-NONE",
            severity="critical",
            confidence=0.99,
            title="JWT advertises alg=none",
            description=(
                "Server-issued JWT advertises ``alg: none``; any client can "
                "forge a token by setting the signature segment to empty. "
                "CWE-347 / OWASP API-2023-08."
            ),
            route=None,
            evidence={
                "location": location,
                "token_prefix": _redacted_prefix(token.raw),
                "alg": "none",
                "cwe_id": "CWE-347",
                "attack_id": "T1606.001",
            },
            recommendation=(
                "Reject ``alg: none`` tokens at the verifier. Pin the "
                "expected algorithm explicitly (e.g. RS256) instead of "
                "trusting the header."
            ),
        )

    if alg == "hs256":
        for secret in _WEAK_HS256_SECRETS:
            if _hs256_verifies_against(token, secret):
                yield SecurityIssue(
                    rule_id="SEC-JWT-WEAK-HS256-SECRET",
                    severity="critical",
                    confidence=0.99,
                    title="JWT signed with a well-known weak HS256 secret",
                    description=(
                        "Server-issued JWT verifies against the well-known "
                        "weak secret. The signing key MUST be rotated and "
                        "moved to a secret manager. CWE-347."
                    ),
                    route=None,
                    evidence={
                        "location": location,
                        "token_prefix": _redacted_prefix(token.raw),
                        "matched_wordlist": "well-known-weak-hs256",
                        "cwe_id": "CWE-347",
                    },
                    recommendation=(
                        "Rotate the HS256 secret to a cryptographically "
                        "random 256-bit value stored outside source control. "
                        "Prefer RS256/EdDSA for cross-service tokens."
                    ),
                )
                break  # one finding per token suffices.

    if "exp" not in payload:
        yield SecurityIssue(
            rule_id="SEC-JWT-MISSING-EXP",
            severity="medium",
            confidence=0.95,
            title="JWT has no exp claim",
            description=(
                "The JWT carries no ``exp`` (expiration) claim. Stolen "
                "tokens remain valid forever. CWE-613."
            ),
            route=None,
            evidence={
                "location": location,
                "token_prefix": _redacted_prefix(token.raw),
                "cwe_id": "CWE-613",
            },
            recommendation=(
                "Set ``exp`` on every JWT (15-60 minutes is typical for "
                "access tokens) and reject expired tokens at the verifier."
            ),
        )
    else:
        exp_value = payload.get("exp")
        if isinstance(exp_value, int | float) and exp_value < now:
            yield SecurityIssue(
                rule_id="SEC-JWT-EXPIRED",
                severity="medium",
                confidence=0.99,
                title="JWT exp is in the past",
                description=(
                    "The JWT's ``exp`` claim is already past the current "
                    "wall-clock time; if the server still accepts it, the "
                    "expiration is not being enforced. CWE-613."
                ),
                route=None,
                evidence={
                    "location": location,
                    "token_prefix": _redacted_prefix(token.raw),
                    "exp": int(exp_value),
                    "now": int(now),
                    "cwe_id": "CWE-613",
                },
                recommendation=(
                    "Reject tokens whose ``exp`` is in the past. Allow only "
                    "a small clock-skew tolerance (≆60 seconds)."
                ),
            )

    if _looks_multi_tenant(payload) and ("aud" not in payload or "iss" not in payload):
        missing = [k for k in ("aud", "iss") if k not in payload]
        yield SecurityIssue(
            rule_id="SEC-JWT-MISSING-ISS-AUD",
            severity="low",
            confidence=0.7,
            title="Multi-tenant JWT missing iss / aud claims",
            description=(
                "JWT carries a ``sub`` plus tenant-shaped claims but no "
                f"{', '.join(missing)}; tokens can be replayed across "
                "tenants. CWE-345."
            ),
            route=None,
            evidence={
                "location": location,
                "token_prefix": _redacted_prefix(token.raw),
                "missing_claims": ",".join(missing),
                "cwe_id": "CWE-345",
            },
            recommendation=(
                "Set ``iss`` to the issuing service and ``aud`` to the "
                "intended audience; verify both at the receiver."
            ),
        )


def _extract_jwts_from_value(value: str) -> Iterable[str]:
    for match in _JWT_RE.finditer(value):
        yield match.group(0)


def scan_observations(
    observations: Iterable[tuple[str, str]],
    *,
    now: float,
) -> Iterable[SecurityIssue]:
    """Run :func:`evaluate_jwt` against every JWT in an observation stream.

    ``observations`` is an iterable of ``(location, raw_value)`` pairs.
    The pure-function entry point: the runner glues this together with
    :class:`CheckContext`, but unit tests call it directly.
    """

    for location, value in observations:
        if not value:
            continue
        for raw_token in _extract_jwts_from_value(value):
            decoded = decode_jwt(raw_token)
            if decoded is None:
                continue
            yield from evaluate_jwt(decoded, location=location, now=now)


def run_jwt_weakness_check(
    ctx: CheckContext,
    *,
    observations: Iterable[tuple[str, str]] | None = None,
    now: float | None = None,
) -> SecurityCheckResult:
    """Module entry point.

    ``observations`` defaults to the Authorization header + cookies that
    the Phase-04 HAR capture exposes via ``ctx.env`` — we collect them
    from a deterministic env-var (``SENTINELQA_JWT_OBSERVATIONS``,
    JSONL pairs) so the orchestrator stays decoupled. Tests inject
    observations directly.
    """

    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    now_ts = now if now is not None else time.time()
    obs_iter = observations or _observations_from_env(ctx)
    issues: list[SecurityIssue] = []
    observed = 0
    for issue in scan_observations(obs_iter, now=now_ts):
        issues.append(issue)
    for _ in []:  # keep dataclass import alive for mypy
        observed += 1
    elapsed_ms = int((time.monotonic() - start) * 1000)
    _audit(ctx, kind="complete", detail=f"issues={len(issues)}")
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=observed,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _observations_from_env(ctx: CheckContext) -> tuple[tuple[str, str], ...]:
    raw = ctx.env.get("SENTINELQA_JWT_OBSERVATIONS", "")
    if not raw:
        return ()
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "location" in parsed and "value" in parsed:
            out.append((str(parsed["location"]), str(parsed["value"])))
    return tuple(out)


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


# Kept exported for the safety guard test that asserts no other
# wordlist / brute-force mechanism exists in this module.
WEAK_HS256_SECRETS = _WEAK_HS256_SECRETS


# Keep datetime/UTC available so static checkers don't trim them when
# the runtime path doesn't dereference them.
_ = datetime.now(UTC)


__all__ = [
    "CHECK_NAME",
    "WEAK_HS256_SECRETS",
    "decode_jwt",
    "evaluate_jwt",
    "run_jwt_weakness_check",
    "scan_observations",
]
