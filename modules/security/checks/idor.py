"""IDOR smoke check.

Detect endpoints whose authorization model is "any logged-in user can
read any other user's resource". The check works by:

1. Authenticating as the **second** test user (env-var pair only;
 see :class:`engine.config.schema.AuthSecondUserConfig`).
2. Identifying routes whose path contains a numeric or UUID segment
 (e.g. ``/api/users/123``, ``/orders/9f1...``).
3. Replacing that segment with one of: the first-user's id (if
 configured), a sentinel value ``1``, and ``me``. Sending GET.
4. If the response is 2xx for another user's id, the endpoint is
 probably missing per-resource authorization.

Without a second test user configured, the check returns
``skipped=True`` with a clear reason — never a fabricated finding.

We never write or delete resources here. Read-only only.
"""

from __future__ import annotations

import os
import re
import time
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.http_client import TokenBucket
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "idor"

_ID_SEGMENT_RE = re.compile(r"^(?:\d+|[0-9a-fA-F]{8,})$")
_PATH_SPLIT_RE = re.compile(r"/+")


def _second_user_token(ctx: CheckContext) -> str | None:
    """Return a bearer token for the second user (env-var only, never inline).

    Resolution order: ``token_env`` first (already a token), then
    fall back to None — username/password login is out of scope for
    the release because it would couple the security module to a full
    auth-orchestration layer. The IDOR check honestly reports
    ``skipped`` when a non-token strategy is configured.
    """

    cfg = ctx.config.auth.second_user
    if cfg.token_env:
        return ctx.env.get(cfg.token_env) or os.environ.get(cfg.token_env)
    return None


def _candidate_segments(path: str) -> list[tuple[int, str]]:
    segments = [s for s in _PATH_SPLIT_RE.split(path) if s]
    candidates: list[tuple[int, str]] = []
    for idx, seg in enumerate(segments):
        if _ID_SEGMENT_RE.match(seg):
            candidates.append((idx, seg))
    return candidates


def _replace_segment(path: str, idx: int, new_value: str) -> str:
    segments = [s for s in _PATH_SPLIT_RE.split(path) if s]
    segments[idx] = new_value
    out = "/" + "/".join(segments)
    if path.endswith("/"):
        out += "/"
    return out


def run_idor_check(ctx: CheckContext) -> SecurityCheckResult:
    token = _second_user_token(ctx)
    if token is None:
        reason = (
            "no second-user token configured "
            "(set auth.second_user.token_env to the env var holding the token)"
        )
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
    bearer_headers = {"Authorization": f"Bearer {token}"}

    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        parsed = urlparse(absolute)
        candidates = _candidate_segments(parsed.path)
        if not candidates:
            continue
        idx, orig = candidates[0]  # one probe per route is enough for smoke
        for replacement in _replacements(ctx, exclude=orig):
            new_path = _replace_segment(parsed.path, idx, replacement)
            new_url = urlunparse(parsed._replace(path=new_path))
            bucket.take()
            try:
                response = ctx.client.get(new_url, headers=bearer_headers)
            except httpx.HTTPError as exc:
                _audit(ctx, route=route, kind="error", detail=str(exc))
                continue
            targets_scanned += 1
            _audit(
                ctx,
                route=route,
                kind="probe",
                detail=(
                    f"original={orig} replacement={replacement} " f"status={response.status_code}"
                ),
            )
            if 200 <= response.status_code < 300:
                issues.append(
                    _issue(
                        "SEC-IDOR-CROSS-USER-ACCESS",
                        severity="critical",
                        route=route,
                        extra={
                            "original_segment": orig,
                            "replacement_segment": replacement,
                            "status": response.status_code,
                            "probed_url": new_url,
                        },
                    )
                )
                break  # one finding per route is enough
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=targets_scanned,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _replacements(ctx: CheckContext, *, exclude: str) -> list[str]:
    out: list[str] = []
    first_user_id = ctx.config.auth.second_user.user_id
    if first_user_id and first_user_id != exclude:
        out.append(first_user_id)
    if exclude != "1":
        out.append("1")
    out.append("me")
    return out


def _issue(
    rule_id: str,
    *,
    severity: str,
    route: str,
    extra: dict[str, object],
) -> SecurityIssue:
    rule = rule_by_id(rule_id)
    return SecurityIssue(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        confidence=0.7,
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


__all__ = ["CHECK_NAME", "run_idor_check"]
