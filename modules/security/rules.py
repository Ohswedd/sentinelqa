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
    # ---------------- Phase 32 — JWT weakness ----------------
    SecurityRule(
        rule_id="SEC-JWT-ALG-NONE",
        category="security/jwt_weakness/sec-jwt-alg-none",
        name="JwtAlgNone",
        title="JWT advertises alg=none",
        description=(
            "Server-issued JWT advertises the unsigned `alg: none` "
            "algorithm. Any client can forge a token by submitting an "
            "empty signature segment. CWE-347."
        ),
        recommendation=("Reject `alg: none` at the verifier; pin the expected algorithm."),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-JWT-WEAK-HS256-SECRET",
        category="security/jwt_weakness/sec-jwt-weak-hs256-secret",
        name="JwtWeakHs256Secret",
        title="JWT signed with a well-known weak HS256 secret",
        description=(
            "Server-issued JWT verifies against one of the well-known "
            "weak HS256 secrets (e.g. `secret`, `password`). The signing "
            "key MUST be rotated to a 256-bit random value. CWE-347."
        ),
        recommendation=(
            "Rotate the HS256 secret to a cryptographically random "
            "256-bit value held in a secret manager."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-JWT-MISSING-EXP",
        category="security/jwt_weakness/sec-jwt-missing-exp",
        name="JwtMissingExp",
        title="JWT has no exp claim",
        description=(
            "The JWT carries no `exp` (expiration) claim. Stolen tokens "
            "remain valid forever. CWE-613."
        ),
        recommendation="Set `exp` on every JWT and reject expired tokens.",
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-JWT-EXPIRED",
        category="security/jwt_weakness/sec-jwt-expired",
        name="JwtExpired",
        title="JWT exp is in the past",
        description=(
            "JWT's `exp` claim is past the current wall-clock time but "
            "the server still surfaced it; expiration is not being "
            "enforced. CWE-613."
        ),
        recommendation=(
            "Reject tokens whose `exp` is in the past with a small " "clock-skew tolerance."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-JWT-MISSING-ISS-AUD",
        category="security/jwt_weakness/sec-jwt-missing-iss-aud",
        name="JwtMissingIssAud",
        title="Multi-tenant JWT missing iss / aud claims",
        description=(
            "JWT carries multi-tenant claims but no `iss` or `aud`; "
            "tokens can be replayed across tenants. CWE-345."
        ),
        recommendation=(
            "Set `iss` to the issuing service and `aud` to the intended "
            "audience; verify both at the receiver."
        ),
        default_severity="note",
    ),
    # ---------------- Phase 32 — Cookie security extended ----------------
    SecurityRule(
        rule_id="SEC-COOKIE-MISSING-PREFIX",
        category="security/cookies/sec-cookie-missing-prefix",
        name="CookieMissingPrefix",
        title="Session cookie missing __Host- / __Secure- prefix",
        description=(
            "A session-shaped cookie was set without the `__Host-` or "
            "`__Secure-` cookie name prefix. The prefixes bind the cookie "
            "to the exact host and to HTTPS-only contexts. CWE-1004."
        ),
        recommendation=(
            "Rename auth cookies with the `__Host-` prefix (Path=/ and no "
            "Domain) or `__Secure-` prefix for cross-subdomain auth."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-COOKIE-OVERBROAD-DOMAIN",
        category="security/cookies/sec-cookie-overbroad-domain",
        name="CookieOverbroadDomain",
        title="Cookie Domain attribute is over-broad",
        description=(
            "A cookie set on a sub-domain declared `Domain=.parent.tld`, "
            "making it readable by every sibling sub-domain. CWE-1275."
        ),
        recommendation=(
            "Scope the cookie's `Domain` to exactly the host that needs "
            "it (or omit `Domain` so the browser uses the strict default)."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-COOKIE-OVERBROAD-PATH",
        category="security/cookies/sec-cookie-overbroad-path",
        name="CookieOverbroadPath",
        title="Sensitive cookie scoped to Path=/",
        description=(
            "A sensitive-looking cookie was scoped to `Path=/`. Path "
            "scoping is a small defence-in-depth measure for "
            "single-purpose cookies. CWE-1275."
        ),
        recommendation=(
            "Scope the cookie's `Path` to exactly the route family that "
            "consumes it (e.g. `/admin`)."
        ),
        default_severity="note",
    ),
    # ---------------- Phase 32 — TLS posture ----------------
    SecurityRule(
        rule_id="SEC-TLS-VERSION-LEGACY",
        category="security/tls_posture/sec-tls-version-legacy",
        name="TlsVersionLegacy",
        title="TLS handshake negotiated a legacy protocol",
        description=(
            "The TLS handshake negotiated a deprecated protocol version "
            "(TLS 1.0, 1.1 or SSLv3). Modern clients should reject these. "
            "CWE-326."
        ),
        recommendation="Disable TLS 1.0 / 1.1 / SSLv3 on the server.",
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-TLS-WEAK-CIPHER",
        category="security/tls_posture/sec-tls-weak-cipher",
        name="TlsWeakCipher",
        title="TLS handshake negotiated a weak cipher suite",
        description=(
            "The TLS handshake negotiated a cipher suite that is "
            "considered weak by modern standards (RC4 / DES / 3DES / "
            "NULL / EXPORT, or CBC-mode with TLS 1.2). CWE-326."
        ),
        recommendation=(
            "Restrict the server's cipher list to AEAD suites " "(GCM / CHACHA20-POLY1305)."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-TLS-CERT-EXPIRED",
        category="security/tls_posture/sec-tls-cert-expired",
        name="TlsCertExpired",
        title="TLS leaf certificate is expired",
        description=(
            "The presented leaf certificate's `notAfter` is in the past. "
            "Browsers will refuse to connect. CWE-295."
        ),
        recommendation="Renew and deploy the certificate immediately.",
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-TLS-CERT-EXPIRING-SOON",
        category="security/tls_posture/sec-tls-cert-expiring-soon",
        name="TlsCertExpiringSoon",
        title="TLS leaf certificate expires within 14 days",
        description=(
            "The presented leaf certificate's `notAfter` is less than 14 "
            "days away. Schedule a renewal. CWE-295."
        ),
        recommendation="Renew the certificate before it expires.",
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-TLS-HSTS-MISSING",
        category="security/tls_posture/sec-tls-hsts-missing",
        name="TlsHstsMissing",
        title="HTTPS endpoint did not return HSTS",
        description=(
            "No `Strict-Transport-Security` header was returned over "
            "HTTPS. Without HSTS, downgrade attacks remain feasible. "
            "CWE-319."
        ),
        recommendation=(
            "Send `Strict-Transport-Security: max-age=31536000; "
            "includeSubDomains` on every HTTPS response."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-TLS-HSTS-TOO-SHORT",
        category="security/tls_posture/sec-tls-hsts-too-short",
        name="TlsHstsTooShort",
        title="HSTS max-age is under one year",
        description=(
            "The `Strict-Transport-Security` `max-age` is below the "
            "365-day recommendation. Short windows let downgrade windows "
            "re-open. CWE-319."
        ),
        recommendation=(
            "Raise `Strict-Transport-Security` `max-age` to at least " "31536000 (one year)."
        ),
        default_severity="warning",
    ),
    # ---------------- Phase 32 — GraphQL safety ----------------
    SecurityRule(
        rule_id="SEC-GRAPHQL-INTROSPECTION-ENABLED",
        category="security/graphql_safety/sec-graphql-introspection-enabled",
        name="GraphqlIntrospectionEnabled",
        title="GraphQL introspection is reachable in production",
        description=(
            "The canonical introspection query `{ __schema { types { name "
            "} } }` returned the schema. Production deployments should "
            "disable introspection. CWE-200."
        ),
        recommendation=(
            "Disable introspection in production (e.g. Apollo `playground "
            "false` / `introspection false`)."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-GRAPHQL-NO-DEPTH-LIMIT",
        category="security/graphql_safety/sec-graphql-no-depth-limit",
        name="GraphqlNoDepthLimit",
        title="GraphQL endpoint has no query-depth limit",
        description=(
            "A depth-5 nested query was accepted; deeply nested queries "
            "are a classic resource-exhaustion vector. CWE-770."
        ),
        recommendation=(
            "Install a query-depth limiter (e.g. `graphql-depth-limit`) "
            "and cap depth at a reasonable value (≤7 is typical)."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-GRAPHQL-NO-COMPLEXITY-LIMIT",
        category="security/graphql_safety/sec-graphql-no-complexity-limit",
        name="GraphqlNoComplexityLimit",
        title="GraphQL endpoint has no query-complexity limit",
        description=(
            "A query with five aliases for the same field was accepted; "
            "alias-based complexity bombs remain a resource-exhaustion "
            "risk. CWE-770."
        ),
        recommendation=("Install a query-cost analyser (e.g. `graphql-query-complexity`)."),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-GRAPHQL-MUTATION-NO-AUTH",
        category="security/graphql_safety/sec-graphql-mutation-no-auth",
        name="GraphqlMutationNoAuth",
        title="GraphQL mutation accepts anonymous requests",
        description=(
            "An introspected mutation returned a non-error response when "
            "called without authentication. CWE-862."
        ),
        recommendation=(
            "Gate mutations behind authentication; assert the caller's "
            "identity before any state-changing resolver runs."
        ),
        default_severity="error",
    ),
    # ---------------- Phase 32 — OWASP-API BOLA / BFLA ----------------
    SecurityRule(
        rule_id="SEC-BOLA-CROSS-TENANT-READ",
        category="security/api_bola_bfla/sec-bola-cross-tenant-read",
        name="BolaCrossTenantRead",
        title="API endpoint returns identity-A data when called as identity-B",
        description=(
            "An API call captured under identity A returned 200 with "
            "A's payload when replayed under identity B's auth — "
            "object-level authorization is missing. OWASP API-2023-01 "
            "(BOLA). CWE-639."
        ),
        recommendation=(
            "Validate object ownership server-side on every read and "
            "write; never trust client-supplied resource ids alone."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-BFLA-ELEVATED-ACTION",
        category="security/api_bola_bfla/sec-bfla-elevated-action",
        name="BflaElevatedAction",
        title="Admin-shaped endpoint accepts non-admin identity",
        description=(
            "An endpoint scoped to admin returned 2xx when called with "
            "a non-admin identity. OWASP API-2023-03 (BFLA). CWE-863."
        ),
        recommendation=(
            "Enforce role-based authorization before the controller body " "runs; deny by default."
        ),
        default_severity="error",
    ),
    # ---------------- Phase 32 — Secret-in-bundle scanner ----------------
    SecurityRule(
        rule_id="SEC-BUNDLE-SECRET-AWS",
        category="security/bundle_secrets/sec-bundle-secret-aws",
        name="BundleSecretAws",
        title="Possible AWS access key in JS bundle",
        description=(
            "A JS bundle served to the browser contains a string matching "
            "the AWS access-key prefix `AKIA`. CWE-540."
        ),
        recommendation=(
            "Move the credential server-side; invoke AWS via a backend "
            "proxy or use IAM-Role-for-Browser identity flows."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-BUNDLE-SECRET-GCP",
        category="security/bundle_secrets/sec-bundle-secret-gcp",
        name="BundleSecretGcp",
        title="Possible Google API key in JS bundle",
        description=(
            "A JS bundle served to the browser contains a string matching "
            "the Google API key prefix `AIza`. CWE-540."
        ),
        recommendation=(
            "Restrict the API key by HTTP referrer + API scope, or move " "API calls server-side."
        ),
        default_severity="warning",
    ),
    SecurityRule(
        rule_id="SEC-BUNDLE-SECRET-AZURE",
        category="security/bundle_secrets/sec-bundle-secret-azure",
        name="BundleSecretAzure",
        title="Possible Azure subscription key in JS bundle",
        description=(
            "A JS bundle includes a 32-hex string in a subscription-key " "context. CWE-540."
        ),
        recommendation=(
            "Move the subscription key server-side; rotate the exposed " "key immediately."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-BUNDLE-SECRET-STRIPE",
        category="security/bundle_secrets/sec-bundle-secret-stripe",
        name="BundleSecretStripe",
        title="Stripe live secret key in JS bundle",
        description=(
            "A JS bundle contains a `sk_live_…` Stripe secret key. "
            "Anyone with the page source can issue arbitrary Stripe "
            "API calls. CWE-540."
        ),
        recommendation=(
            "Rotate the Stripe key immediately and route Stripe API " "calls through your backend."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-BUNDLE-SECRET-GITHUB",
        category="security/bundle_secrets/sec-bundle-secret-github",
        name="BundleSecretGithub",
        title="GitHub token in JS bundle",
        description=("A JS bundle contains a `ghp_…` / `gho_…` GitHub token. " "CWE-540."),
        recommendation=(
            "Rotate the token immediately; route GitHub API calls " "through a server-side proxy."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-BUNDLE-SECRET-SLACK",
        category="security/bundle_secrets/sec-bundle-secret-slack",
        name="BundleSecretSlack",
        title="Slack token in JS bundle",
        description=("A JS bundle contains a Slack `xox[abprs]-` token. CWE-540."),
        recommendation=(
            "Rotate the Slack token immediately; never embed Slack " "tokens in browser code."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-BUNDLE-SECRET-PRIVATE-KEY",
        category="security/bundle_secrets/sec-bundle-secret-private-key",
        name="BundleSecretPrivateKey",
        title="PEM private-key header in JS bundle",
        description=(
            "A JS bundle contains a `-----BEGIN ... PRIVATE KEY-----` " "header. CWE-540."
        ),
        recommendation=(
            "Rotate the key immediately; private keys must never reach " "the browser."
        ),
        default_severity="error",
    ),
    # ---------------- Phase 32 — SSRF / open-redirect ----------------
    SecurityRule(
        rule_id="SEC-SSRF-SUSPECTED",
        category="security/ssrf_redirect/sec-ssrf-suspected",
        name="SsrfSuspected",
        title="Endpoint may follow attacker-controlled URLs (SSRF)",
        description=(
            "A URL-shaped form / query parameter accepted a canonical "
            "internal target (loopback, link-local, file://) without a "
            "clean rejection. CWE-918."
        ),
        recommendation=(
            "Validate that user-supplied URLs resolve outside the "
            "server's local network; deny `127.0.0.0/8`, `169.254.0.0/16`, "
            "`fc00::/7`, and all non-HTTP schemes."
        ),
        default_severity="error",
    ),
    SecurityRule(
        rule_id="SEC-OPEN-REDIRECT",
        category="security/ssrf_redirect/sec-open-redirect",
        name="OpenRedirect",
        title="Redirect endpoint accepts attacker-controlled destination",
        description=(
            "A redirect endpoint emitted a 30x with an attacker-supplied "
            "URL in `Location`. CWE-601."
        ),
        recommendation=(
            "Restrict redirect destinations to an allowlist of known "
            "callback URLs; reject `//evil.example.com`-style inputs."
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
