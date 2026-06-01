"""Cookie-flags check.

We GET each route once and inspect every ``Set-Cookie`` header for the
``HttpOnly``, ``Secure`` (HTTPS), and ``SameSite`` attributes. Auth-
looking cookies (name matches ``session|auth|jwt|token`` or set on a
login response — we use the name heuristic for the release) escalate the
severity to ``high``.

the engineering guidelines: cookie *values* never leave the process — we read the
attributes only and never log or persist the value.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id

CHECK_NAME = "cookies"

_AUTH_COOKIE_RE = re.compile(r"(?:session|sess|auth|jwt|token|sid)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _ParsedCookie:
    name: str
    attributes: frozenset[str]
    samesite: str | None
    domain: str | None = None
    path: str | None = None

    @property
    def is_auth_like(self) -> bool:
        return bool(_AUTH_COOKIE_RE.search(self.name))

    @property
    def has_host_prefix(self) -> bool:
        return self.name.startswith("__Host-")

    @property
    def has_secure_prefix(self) -> bool:
        return self.name.startswith("__Secure-")


def parse_set_cookie(raw: str) -> _ParsedCookie:
    """Parse a ``Set-Cookie`` header value (RFC 6265 attribute model).

    We do *not* honour quoted commas inside values; httpx already splits
    multi-cookie ``Set-Cookie`` headers for us when they come back from
    the wire. Quote handling is intentionally minimal because we never
    persist or surface the cookie value.
    """

    head, _, _ = raw.partition(",")
    parts = [p.strip() for p in head.split(";") if p.strip()]
    if not parts:
        return _ParsedCookie(name="", attributes=frozenset(), samesite=None)
    nv = parts[0]
    name, _, _value = nv.partition("=")
    attributes: set[str] = set()
    samesite: str | None = None
    domain: str | None = None
    path: str | None = None
    for token in parts[1:]:
        if "=" in token:
            attr_name, _, attr_val = token.partition("=")
            attr_name = attr_name.strip().lower()
            attr_val = attr_val.strip()
            if attr_name == "samesite":
                samesite = attr_val.lower()
            elif attr_name == "domain":
                domain = attr_val.lstrip(".").lower() if attr_val else None
                # Track the leading dot so over-broad detection can fire
                # on ``Domain=.parent.tld``.
                if attr_val.startswith("."):
                    attributes.add("domain-leading-dot")
            elif attr_name == "path":
                path = attr_val
            attributes.add(attr_name)
        else:
            attributes.add(token.strip().lower())
    return _ParsedCookie(
        name=name.strip(),
        attributes=frozenset(attributes),
        samesite=samesite,
        domain=domain,
        path=path,
    )


def evaluate_cookie(
    cookie: _ParsedCookie,
    *,
    route: str,
    is_https: bool,
    response_host: str | None = None,
) -> Iterable[SecurityIssue]:
    """Yield issues for one cookie."""

    if not cookie.name:
        return
    severity_for = "high" if cookie.is_auth_like else "medium"

    if "httponly" not in cookie.attributes:
        yield _issue(
            "SEC-COOKIE-MISSING-HTTPONLY",
            severity=severity_for,
            route=route,
            extra={"cookie_name": cookie.name, "auth_like": cookie.is_auth_like},
        )
    if is_https and "secure" not in cookie.attributes:
        yield _issue(
            "SEC-COOKIE-MISSING-SECURE",
            severity=severity_for,
            route=route,
            extra={"cookie_name": cookie.name, "auth_like": cookie.is_auth_like},
        )
    if cookie.samesite is None:
        yield _issue(
            "SEC-COOKIE-MISSING-SAMESITE",
            severity="medium" if cookie.is_auth_like else "low",
            route=route,
            extra={"cookie_name": cookie.name, "auth_like": cookie.is_auth_like},
        )
    elif cookie.samesite == "none" and "secure" not in cookie.attributes:
        yield _issue(
            "SEC-COOKIE-SAMESITE-NONE-WITHOUT-SECURE",
            severity="high",
            route=route,
            extra={"cookie_name": cookie.name},
        )

    # ---------- extended rules (ADR-0044) ----------
    if cookie.is_auth_like and not (cookie.has_host_prefix or cookie.has_secure_prefix):
        yield _issue(
            "SEC-COOKIE-MISSING-PREFIX",
            severity="medium",
            route=route,
            extra={
                "cookie_name": cookie.name,
                "expected_prefix": "__Host-" if "domain" not in cookie.attributes else "__Secure-",
                "cwe_id": "CWE-1004",
            },
        )
    if (
        cookie.domain is not None
        and response_host is not None
        and "domain-leading-dot" in cookie.attributes
        and cookie.domain != response_host.lower()
        and response_host.lower().endswith("." + cookie.domain)
    ):
        yield _issue(
            "SEC-COOKIE-OVERBROAD-DOMAIN",
            severity="medium",
            route=route,
            extra={
                "cookie_name": cookie.name,
                "domain": cookie.domain,
                "response_host": response_host.lower(),
                "cwe_id": "CWE-1275",
            },
        )
    # __Host- prefix REQUIRES Path=/ (RFC 6265bis); only fire overbroad-path
    # when the cookie isn't relying on the prefix to enforce host binding.
    if cookie.path == "/" and cookie.is_auth_like and not cookie.has_host_prefix:
        yield _issue(
            "SEC-COOKIE-OVERBROAD-PATH",
            severity="low",
            route=route,
            extra={
                "cookie_name": cookie.name,
                "path": cookie.path,
                "cwe_id": "CWE-1275",
            },
        )


def run_cookies_check(ctx: CheckContext) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        parsed = urlparse(absolute)
        is_https = parsed.scheme == "https"
        try:
            response = ctx.client.get(absolute)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="error", detail=str(exc))
            continue
        targets_scanned += 1
        _audit(ctx, route=route, kind="probe", detail=f"status={response.status_code}")
        # httpx splits Set-Cookie into multiple header entries automatically.
        response_host = parsed.hostname
        for raw in response.headers.get_list("set-cookie"):
            cookie = parse_set_cookie(raw)
            for issue in evaluate_cookie(
                cookie,
                route=route,
                is_https=is_https,
                response_host=response_host,
            ):
                issues.append(issue)
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
    extra: dict[str, object] | None = None,
) -> SecurityIssue:
    rule = rule_by_id(rule_id)
    return SecurityIssue(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        confidence=0.95,
        title=rule.title,
        description=rule.description,
        route=route,
        evidence=dict(extra or {}),
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
    "parse_set_cookie",
    "evaluate_cookie",
    "run_cookies_check",
]
