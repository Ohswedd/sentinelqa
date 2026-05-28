"""Stored-XSS safe probe (Phase 13.05, gated).

This check is **off by default** and ONLY runs when ALL of the following
hold (CLAUDE §6, §26 + PRD §2):

- ``config.security.mode == "authorized_destructive"``.
- ``config.security.checks.xss_stored`` is true.
- ``config.target.proof_of_authorization`` points at a valid proof doc.

When any precondition is missing, the check returns a ``skipped=True``
result with an explanatory reason (it never silently passes — CLAUDE
§37 forbids fake completion).

The probe submits a unique non-executable marker into the first
discoverable form on each route; the GET that follows checks the same
route's response body for the marker. As with reflected XSS, the
marker is the literal string ``__SENTINELQA_STORED_XSS__`` embedded
in ``<svg/onload=...>`` — non-executable but easy to grep for.

The probe never escalates privilege, deletes data, or writes outside
the explicitly-targeted form fields. It is conservative on purpose:
its job is to find the obvious "no escaping anywhere" bug, not to
prove an exploitable XSS chain.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import httpx
from engine.errors.base import ConfigError, DestructiveWithoutProofError
from engine.policy.audit_log import write_audit_entry
from engine.policy.proof_of_authorization import require_proof
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.checks.xss_reflected import _has_reflection
from modules.security.http_client import TokenBucket
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "xss_stored"

MARKER = "__SENTINELQA_STORED_XSS__"
PAYLOAD = f"<svg/onload={MARKER}>"

_FORM_RE = re.compile(
    r"<form\b([^>]*)>(.*?)</form>",
    re.IGNORECASE | re.DOTALL,
)
_ACTION_RE = re.compile(r"""action\s*=\s*['"]?(?P<a>[^'"\s>]+)['"]?""", re.IGNORECASE)
_METHOD_RE = re.compile(r"""method\s*=\s*['"]?(?P<m>[A-Za-z]+)['"]?""", re.IGNORECASE)
_INPUT_RE = re.compile(
    r"""<(?:input|textarea)\b[^>]*?\bname\s*=\s*['"](?P<name>[^'"]+)['"][^>]*?(?:type\s*=\s*['"](?P<type>[^'"]+)['"])?""",
    re.IGNORECASE,
)

_SAFE_TYPES = {"text", "textarea", "search", "url", ""}


def _allowed_to_run(ctx: CheckContext) -> tuple[bool, str]:
    if not ctx.config.security.checks.xss_stored:
        return False, "config.security.checks.xss_stored is false"
    if ctx.config.security.mode != "authorized_destructive":
        return False, "security.mode != 'authorized_destructive'"
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


def run_xss_stored_check(ctx: CheckContext) -> SecurityCheckResult:
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
    rate = ctx.config.security.max_requests_per_second
    bucket = TokenBucket(rate_per_second=float(rate))

    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        bucket.take()
        try:
            get_response = ctx.client.get(absolute)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="error", detail=str(exc))
            continue
        body = get_response.text or ""
        form_match = _FORM_RE.search(body)
        if form_match is None:
            continue
        attrs, inner = form_match.group(1) or "", form_match.group(2) or ""
        action_match = _ACTION_RE.search(attrs)
        method_match = _METHOD_RE.search(attrs)
        method = (method_match.group("m") if method_match else "POST").upper()
        if method not in {"POST", "PUT", "PATCH"}:
            continue
        action_url = urljoin(absolute, action_match.group("a")) if action_match else absolute
        fields: dict[str, str] = {}
        for input_match in _INPUT_RE.finditer(inner):
            name = input_match.group("name") or ""
            type_ = (input_match.group("type") or "").lower()
            if type_ in _SAFE_TYPES:
                fields[name] = PAYLOAD
            else:
                fields[name] = ""
        if not fields:
            continue
        bucket.take()
        try:
            post_response = ctx.client.request(method, action_url, data=fields)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="post_error", detail=str(exc))
            continue
        targets_scanned += 1
        _audit(
            ctx,
            route=route,
            kind="probe",
            detail=(f"action={action_url} method={method} status={post_response.status_code}"),
        )
        bucket.take()
        try:
            follow = ctx.client.get(absolute)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="reload_error", detail=str(exc))
            continue
        follow_body = follow.text or ""
        if _has_reflection(follow_body, MARKER):
            issues.append(
                _issue(
                    "SEC-XSS-STORED",
                    severity="critical",
                    route=route,
                    extra={
                        "form_action": action_url,
                        "form_method": method,
                        "marker": MARKER,
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


def _issue(rule_id: str, *, severity: str, route: str, extra: dict[str, object]) -> SecurityIssue:
    rule = rule_by_id(rule_id)
    return SecurityIssue(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        confidence=0.95,
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


__all__ = ["CHECK_NAME", "MARKER", "PAYLOAD", "run_xss_stored_check"]
