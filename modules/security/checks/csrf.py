"""CSRF check (Phase 13.04).

For each form discovered at a route (we GET the route and parse
``<form>`` elements with ``method=post|put|patch|delete``), we look for:

- A hidden input whose name contains ``csrf`` / ``xsrf`` / ``_token``.
- An action that matches ``X-CSRF-Token`` / ``X-XSRF-Token`` meta tag
  emission.

If neither exists AND the cookies returned with the form lack
``SameSite=Lax|Strict``, we emit a high-severity CSRF finding.

Without a credentialed session we cannot fully exercise the CSRF flow,
so this check is intentionally conservative: it's a smoke check that
flags the obvious "no protection at all" misconfig, not a definitive
test.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.checks.cookies import parse_set_cookie
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "csrf"

_FORM_RE = re.compile(
    r"<form\b([^>]*)>(.*?)</form>",
    re.IGNORECASE | re.DOTALL,
)
_METHOD_RE = re.compile(r"""method\s*=\s*['"]?(?P<m>[A-Za-z]+)['"]?""", re.IGNORECASE)
_INPUT_NAME_RE = re.compile(
    r"""<input\b[^>]*\bname\s*=\s*['"](?P<name>[^'"]+)['"]""",
    re.IGNORECASE,
)
_META_CSRF_RE = re.compile(
    r"""<meta\b[^>]*\bname\s*=\s*['"](?:csrf-token|csrf|x-csrf-token|x-xsrf-token)['"]""",
    re.IGNORECASE,
)
_CSRF_FIELD_RE = re.compile(r"(?:^|_)(?:csrf|xsrf|_token|authenticity_token)\b", re.IGNORECASE)


def _form_has_csrf_token(body: str) -> bool:
    return any(_CSRF_FIELD_RE.search(name) for name in _INPUT_NAME_RE.findall(body))


def _page_has_csrf_meta(html: str) -> bool:
    return bool(_META_CSRF_RE.search(html))


def _samesite_protects(cookie_headers: list[str]) -> bool:
    for raw in cookie_headers:
        cookie = parse_set_cookie(raw)
        if cookie.samesite in {"lax", "strict"}:
            return True
    return False


def run_csrf_check(ctx: CheckContext) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        try:
            response = ctx.client.get(absolute)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="error", detail=str(exc))
            continue
        targets_scanned += 1
        _audit(ctx, route=route, kind="probe", detail=f"status={response.status_code}")
        body = response.text or ""
        cookie_headers = response.headers.get_list("set-cookie")
        meta_protects = _page_has_csrf_meta(body)
        samesite_protects = _samesite_protects(cookie_headers)
        for match in _FORM_RE.finditer(body):
            attrs, inner = match.group(1) or "", match.group(2) or ""
            method_match = _METHOD_RE.search(attrs)
            method = (method_match.group("m") if method_match else "GET").upper()
            if method not in {"POST", "PUT", "PATCH", "DELETE"}:
                continue
            if _form_has_csrf_token(inner) or meta_protects:
                continue
            if samesite_protects:
                continue
            issues.append(
                _issue(
                    "SEC-CSRF-MISSING-TOKEN",
                    severity="high",
                    route=route,
                    extra={
                        "form_method": method,
                        "samesite_protected": samesite_protects,
                        "meta_csrf_token": meta_protects,
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


__all__ = ["CHECK_NAME", "run_csrf_check"]
