"""Security rule catalog + SARIF registration (Phase 13.10, ADR-0018).

Every security finding carries a stable ``rule_id`` (e.g.
``SEC-HEADERS-HSTS-MISSING``) so consumers can correlate findings
across runs and SARIF readers can show curated documentation. The
catalog below is the single source of truth; the SARIF writer
(:mod:`engine.reporter.sarif_writer`) asks
:class:`engine.reporter.sarif_rules.SarifRuleRegistry` for descriptors
by category (e.g. ``security/headers/hsts_missing``), and the
``register_security_rules`` function below populates that registry
exactly once per process.

Each rule's ``help_uri`` points at the SentinelQA docs (Phase 27);
the URL is stable so security-team dashboards can deep-link.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from engine.reporter.sarif_rules import (
    SarifRule,
    SarifRuleRegistry,
    default_sarif_registry,
)

# Convention: ``SEC-<CHECK>-<DETAIL>``. Detail is uppercase, hyphen-
# separated, and stable across releases — changing a rule id is a
# breaking change for downstream dashboards.

_HELP_BASE: Final[str] = "https://docs.sentinelqa.dev/rules/security/"


@dataclass(frozen=True, slots=True)
class SecurityRule:
    """In-process catalog entry for a security rule.

    Mirrors :class:`engine.reporter.sarif_rules.SarifRule` but carries
    a ``recommendation`` field (used by the SDK + HTML report) and the
    category-string the writer keys on.
    """

    rule_id: str
    category: str
    name: str
    title: str
    description: str
    recommendation: str
    default_severity: str = "warning"
    """SARIF severity level (`note` / `warning` / `error`)."""

    @property
    def help_uri(self) -> str:
        slug = self.rule_id.lower().replace("_", "-")
        return f"{_HELP_BASE}{slug}"

    def to_sarif_rule(self) -> SarifRule:
        return SarifRule(
            id=self.rule_id,
            name=self.name,
            short_description=self.title,
            full_description=self.description,
            help_uri=self.help_uri,
            category=self.category,
            default_severity=self.default_severity,
        )


_RULES: Final[tuple[SecurityRule, ...]] = (
    # ---------------- Headers ----------------
    SecurityRule(
        rule_id="SEC-HEADERS-HSTS-MISSING",
        category="security/headers/hsts_missing",
        name="HstsMissing",
        title="Strict-Transport-Security header missing on HTTPS endpoint",
        description=(
            "The Strict-Transport-Security response header was not present "
            "on an HTTPS route. Without HSTS, an active network attacker "
            "can downgrade subsequent requests to HTTP and intercept them. "
            "OWASP recommends a max-age of at least 31536000 seconds."
        ),
        recommendation=(
            "Send `Strict-Transport-Security: max-age=31536000; includeSubDomains` "
            "on every HTTPS response (preload eligibility optional)."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-HEADERS-CSP-MISSING",
        category="security/headers/csp_missing",
        name="ContentSecurityPolicyMissing",
        title="Content-Security-Policy header missing",
        description=(
            "No Content-Security-Policy header was returned. CSP is the "
            "primary defence against XSS by restricting the sources of "
            "executable script. Missing CSP is a high-impact gap for any "
            "endpoint that accepts user input."
        ),
        recommendation=(
            "Return a Content-Security-Policy that at minimum sets "
            "`default-src 'self'` and locks down `script-src`."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-HEADERS-CSP-UNSAFE-INLINE",
        category="security/headers/csp_unsafe_inline",
        name="ContentSecurityPolicyUnsafeInline",
        title="Content-Security-Policy permits unsafe-inline script",
        description=(
            "The Content-Security-Policy header declares `'unsafe-inline'` "
            "(or `'unsafe-eval'`) for `script-src`. Both directives "
            "effectively disable CSP's XSS protections."
        ),
        recommendation=(
            "Remove `'unsafe-inline'` / `'unsafe-eval'`. Use nonces or hashes "
            "for inline scripts, or refactor to external script files."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-HEADERS-XFRAME-MISSING",
        category="security/headers/xframe_missing",
        name="XFrameOptionsMissing",
        title="X-Frame-Options / CSP frame-ancestors missing",
        description=(
            "Neither X-Frame-Options nor a CSP `frame-ancestors` directive "
            "was returned. The response can be embedded in a hostile frame "
            "(clickjacking)."
        ),
        recommendation=(
            "Set `X-Frame-Options: DENY` (or `SAMEORIGIN`) or include "
            "`frame-ancestors 'self'` in CSP."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-HEADERS-XCONTENT-NOSNIFF-MISSING",
        category="security/headers/xcontent_nosniff_missing",
        name="XContentTypeOptionsMissing",
        title="X-Content-Type-Options: nosniff header missing",
        description=(
            "Without `X-Content-Type-Options: nosniff`, MIME-sniffing "
            "browsers may execute responses whose Content-Type is wrong "
            "(e.g. treat a JSON response as JavaScript)."
        ),
        recommendation="Set `X-Content-Type-Options: nosniff` on every response.",
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-HEADERS-REFERRER-POLICY-MISSING",
        category="security/headers/referrer_policy_missing",
        name="ReferrerPolicyMissing",
        title="Referrer-Policy header missing",
        description=(
            "No Referrer-Policy header was returned. Sensitive URLs may "
            "leak to third-party sites via the Referer header."
        ),
        recommendation=(
            "Send `Referrer-Policy: strict-origin-when-cross-origin` or "
            "`no-referrer` for sensitive pages."
        ),
        default_severity="note",
    ),
    SecurityRule(
        rule_id="SEC-HEADERS-PERMISSIONS-POLICY-MISSING",
        category="security/headers/permissions_policy_missing",
        name="PermissionsPolicyMissing",
        title="Permissions-Policy header missing",
        description=(
            "No Permissions-Policy header was returned. The page does not "
            "lock down powerful features (camera, microphone, geolocation, "
            "etc.) for embedded iframes."
        ),
        recommendation=(
            "Send a Permissions-Policy header that disables features the "
            "site does not use (e.g. `camera=(), microphone=(), geolocation=()`)."
        ),
        default_severity="note",
    ),
    # ---------------- Cookies ----------------
    SecurityRule(
        rule_id="SEC-COOKIE-MISSING-SECURE",
        category="security/cookies/missing_secure",
        name="CookieMissingSecure",
        title="Cookie set without Secure flag on HTTPS endpoint",
        description=(
            "A cookie was set without the `Secure` attribute on an HTTPS "
            "response. The cookie can be transmitted over plain HTTP if "
            "the browser is ever tricked into using HTTP for the site."
        ),
        recommendation="Add the `Secure` attribute to every cookie on HTTPS sites.",
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-COOKIE-MISSING-HTTPONLY",
        category="security/cookies/missing_httponly",
        name="CookieMissingHttpOnly",
        title="Cookie set without HttpOnly flag",
        description=(
            "A cookie was set without the `HttpOnly` attribute. JavaScript "
            "running in the page can read the cookie, which makes it an "
            "attractive target for any XSS bug."
        ),
        recommendation=(
            "Add `HttpOnly` to session and authentication cookies so they "
            "are inaccessible from JavaScript."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-COOKIE-MISSING-SAMESITE",
        category="security/cookies/missing_samesite",
        name="CookieMissingSameSite",
        title="Cookie missing SameSite attribute",
        description=(
            "A cookie was set without a `SameSite` attribute. Browsers "
            "default to `Lax`, but explicitly setting `SameSite=Lax` or "
            "`SameSite=Strict` removes the risk of cross-origin CSRF."
        ),
        recommendation=(
            "Set `SameSite=Lax` (default) or `SameSite=Strict` on auth "
            "cookies; use `SameSite=None; Secure` only for cross-site SSO."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-COOKIE-SAMESITE-NONE-WITHOUT-SECURE",
        category="security/cookies/samesite_none_without_secure",
        name="CookieSameSiteNoneWithoutSecure",
        title="Cookie SameSite=None without Secure",
        description=(
            "`SameSite=None` is only honored by modern browsers when the "
            "cookie is also marked `Secure`. Without `Secure`, the cookie "
            "will be silently dropped."
        ),
        recommendation="Always pair `SameSite=None` with `Secure`.",
        default_severity="error",
    ),
    # ---------------- CORS ----------------
    SecurityRule(
        rule_id="SEC-CORS-WILDCARD-CREDENTIALS",
        category="security/cors/wildcard_credentials",
        name="CorsWildcardWithCredentials",
        title="CORS wildcard origin with credentials allowed",
        description=(
            "The server returned `Access-Control-Allow-Origin: *` together "
            "with `Access-Control-Allow-Credentials: true`. Modern browsers "
            "ignore this combination, but legacy clients may honour it and "
            "expose authenticated responses to any origin."
        ),
        recommendation=(
            "Echo a strict allowlist of origins in `Access-Control-Allow-Origin` "
            "(or omit credentials)."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-CORS-REFLECTIVE-ALLOW-ORIGIN",
        category="security/cors/reflective_allow_origin",
        name="CorsReflectiveAllowOrigin",
        title="CORS reflects any origin",
        description=(
            "The server reflected the `Origin` request header in "
            "`Access-Control-Allow-Origin` without an allowlist. Any site "
            "the user visits can read cross-origin responses."
        ),
        recommendation=(
            "Maintain a strict allowlist of trusted origins; never echo "
            "arbitrary `Origin` values."
        ),
        default_severity="error",
    ),
    # ---------------- CSRF ----------------
    SecurityRule(
        rule_id="SEC-CSRF-MISSING-TOKEN",
        category="security/csrf/missing_token",
        name="CsrfMissingToken",
        title="State-changing endpoint missing CSRF token",
        description=(
            "A POST/PUT/PATCH/DELETE endpoint behind authentication does "
            "not appear to require a CSRF token, and the matching auth "
            "cookie was not declared `SameSite=Lax` or `SameSite=Strict`."
        ),
        recommendation=(
            "Add an anti-CSRF token (synchroniser pattern) or set "
            "`SameSite=Lax`/`Strict` on the auth cookie."
        ),
        default_severity="error",
    ),
    # ---------------- XSS ----------------
    SecurityRule(
        rule_id="SEC-XSS-REFLECTED",
        category="security/xss/reflected",
        name="ReflectedXss",
        title="Reflected XSS marker echoed unescaped",
        description=(
            "A harmless SentinelQA marker payload was reflected unescaped "
            "in the response body. Untrusted input is rendered into HTML "
            "without proper escaping."
        ),
        recommendation=(
            "Escape all user-supplied values before inserting them into "
            "HTML. Where dynamic HTML is required, use a templating "
            "library that auto-escapes by default."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-XSS-STORED",
        category="security/xss/stored",
        name="StoredXss",
        title="Stored XSS marker rendered unescaped on subsequent page-load",
        description=(
            "A harmless SentinelQA marker was submitted into a form and "
            "later rendered unescaped on a different page-load. Stored XSS "
            "persists across users and sessions."
        ),
        recommendation=(
            "Sanitise stored content on the way in and escape it on the "
            "way out. Prefer rich-text editors that emit safe HTML."
        ),
        default_severity="error",
    ),
    # ---------------- SQLi ----------------
    SecurityRule(
        rule_id="SEC-SQLI-BEHAVIORAL",
        category="security/sqli/behavioral",
        name="SqliBehavioral",
        title="Endpoint behaviour suggests SQL injection",
        description=(
            "Boolean-true and boolean-false probes produced significantly "
            "different responses, suggesting the parameter is concatenated "
            "into a SQL statement."
        ),
        recommendation=(
            "Switch to parameterised queries (prepared statements). Never "
            "concatenate user input into SQL strings."
        ),
        default_severity="error",
    ),
    # ---------------- IDOR ----------------
    SecurityRule(
        rule_id="SEC-IDOR-CROSS-USER-ACCESS",
        category="security/idor/cross_user_access",
        name="IdorCrossUserAccess",
        title="Endpoint returns another user's resource",
        description=(
            "A path-id endpoint returned a 2xx response when called with "
            "another user's identifier while authenticated as a low-privilege "
            "test user. The endpoint does not enforce object-level access "
            "control."
        ),
        recommendation=(
            "Validate object-level authorization on every read/write: the "
            "resource owner (or an explicit ACL) must match the calling user."
        ),
        default_severity="error",
    ),
    # ---------------- Frontend secrets ----------------
    SecurityRule(
        rule_id="SEC-FRONTEND-SECRET-IN-BUNDLE",
        category="security/frontend/secret_in_bundle",
        name="FrontendSecretInBundle",
        title="Secret-looking value found in JS bundle",
        description=(
            "A SentinelQA detector pattern matched inside a JavaScript "
            "bundle served to the browser. Hardcoded credentials, API "
            "keys, or tokens in client code are recoverable by anyone."
        ),
        recommendation=(
            "Move the secret server-side. Use a backend-for-frontend or "
            "an OAuth token-exchange flow to scope what the browser can do."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-FRONTEND-TOKEN-IN-STORAGE",
        category="security/frontend/token_in_storage",
        name="FrontendTokenInStorage",
        title="Auth token written to localStorage/sessionStorage",
        description=(
            "A JWT, opaque session token, or API key was found in "
            "localStorage / sessionStorage. Tokens stored here are "
            "accessible to any JavaScript that runs in the page, "
            "including XSS payloads."
        ),
        recommendation=(
            "Store auth tokens in HttpOnly+Secure cookies. If a JS-readable "
            "token is unavoidable, minimise lifetime and scope and pair it "
            "with strong CSP."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-FRONTEND-PII-IN-DOM",
        category="security/frontend/pii_in_dom",
        name="FrontendPiiInDom",
        title="Personally-identifiable data found in DOM for anonymous user",
        description=(
            "Email-address or phone-number patterns appeared in the DOM "
            "for a session SentinelQA loaded without authentication. "
            "Anonymous PII exposure may breach data-protection policy."
        ),
        recommendation=(
            "Gate PII rendering behind authentication and authorization "
            "checks; double-check error pages and 404 templates."
        ),
        default_severity="warning",
    ),
    # ---------------- Dependency / SAST ----------------
    SecurityRule(
        rule_id="SEC-DEPS-VULNERABLE",
        category="security/deps/vulnerable",
        name="VulnerableDependency",
        title="Vulnerable dependency detected",
        description=(
            "A dependency scanner (pip-audit / npm audit / osv-scanner) "
            "reported a known-vulnerable package in the lockfile."
        ),
        recommendation=(
            "Upgrade the dependency to the advisory's fixed version, or "
            "remove the package if it is unused."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-SAST-FINDING",
        category="security/sast/finding",
        name="SastFinding",
        title="SAST rule matched in source code",
        description=(
            "A SAST tool (semgrep) reported a code pattern matching one " "of its security rules."
        ),
        recommendation=(
            "Review the matching code and apply the language- or "
            "framework-appropriate hardening (escape, validate, parameterise, "
            "or refactor)."
        ),
        default_severity="warning",
    ),
)


_RULES_BY_ID: Final[dict[str, SecurityRule]] = {r.rule_id: r for r in _RULES}
_RULES_BY_CATEGORY: Final[dict[str, SecurityRule]] = {r.category: r for r in _RULES}


def all_rules() -> tuple[SecurityRule, ...]:
    """Return every registered security rule (catalog order)."""

    return _RULES


def rule_by_id(rule_id: str) -> SecurityRule:
    """Return the catalog entry for ``rule_id``; raises :class:`KeyError`."""

    return _RULES_BY_ID[rule_id]


def rule_by_category(category: str) -> SecurityRule:
    """Return the catalog entry for ``category``; raises :class:`KeyError`."""

    return _RULES_BY_CATEGORY[category]


_REGISTERED: bool = False


def register_security_rules(registry: SarifRuleRegistry | None = None) -> None:
    """Register every catalog entry with the SARIF registry.

    Idempotent: safe to call from ``modules.security.__init__`` or test
    setup. Re-registration on the default registry is a no-op.
    """

    global _REGISTERED
    reg = registry or default_sarif_registry()
    if reg is default_sarif_registry() and _REGISTERED:
        return
    for rule in _RULES:
        if rule.category in reg.known_categories():
            continue
        reg.register(rule.to_sarif_rule())
    if reg is default_sarif_registry():
        _REGISTERED = True


__all__ = [
    "SecurityRule",
    "all_rules",
    "rule_by_id",
    "rule_by_category",
    "register_security_rules",
]
