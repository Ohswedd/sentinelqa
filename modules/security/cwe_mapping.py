"""Default CWE / ATT&CK / OWASP-API mapping for security findings.

Phase 32 / ADR-0044. Every security finding category SHOULD carry a
``cwe_id`` so downstream consumers (SARIF dashboards, the SentinelQA
HTML report, security-team triage queues) can deep-link to canonical
standards. Module-level checks may override per-finding by setting the
fields directly on the :class:`engine.domain.finding.Finding`; this
table is the deterministic default applied by
:func:`modules.security.findings.findings_from_checks` when no explicit
value is set.

The keys are the canonical category prefixes the security module emits
(see :mod:`modules.security.rules`). Lookup is by exact category, with
a fall-through to the longest matching prefix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class TaxonomyIds:
    """Triple of canonical taxonomy identifiers attached to a category."""

    cwe_id: str | None = None
    attack_id: str | None = None
    owasp_api_id: str | None = None


# Keys MUST match the category strings emitted by ``modules.security``
# (``security/<check>/<rule_id_lower>``). Phase-13 + Phase-32 rules are
# all enumerated here; CI test
# ``tests/unit/security/test_cwe_mapping_covers_rules.py`` verifies that
# every registered security ``rule_id`` has a mapping entry.
_DEFAULTS: Final[dict[str, TaxonomyIds]] = {
    # ---------------- Headers (Phase 13) ----------------
    "security/headers/sec-headers-hsts-missing": TaxonomyIds(cwe_id="CWE-319"),
    "security/headers/sec-headers-csp-missing": TaxonomyIds(cwe_id="CWE-693"),
    "security/headers/sec-headers-csp-unsafe-inline": TaxonomyIds(cwe_id="CWE-693"),
    "security/headers/sec-headers-xframe-missing": TaxonomyIds(cwe_id="CWE-1021"),
    "security/headers/sec-headers-xcontent-nosniff-missing": TaxonomyIds(cwe_id="CWE-693"),
    "security/headers/sec-headers-referrer-policy-missing": TaxonomyIds(cwe_id="CWE-200"),
    "security/headers/sec-headers-permissions-policy-missing": TaxonomyIds(cwe_id="CWE-693"),
    # ---------------- Cookies (Phase 13 + Phase 32.02) ----------------
    "security/cookies/sec-cookie-missing-secure": TaxonomyIds(cwe_id="CWE-614"),
    "security/cookies/sec-cookie-missing-httponly": TaxonomyIds(cwe_id="CWE-1004"),
    "security/cookies/sec-cookie-missing-samesite": TaxonomyIds(cwe_id="CWE-1275"),
    "security/cookies/sec-cookie-samesite-none-without-secure": TaxonomyIds(cwe_id="CWE-614"),
    "security/cookies/sec-cookie-missing-prefix": TaxonomyIds(cwe_id="CWE-1004"),
    "security/cookies/sec-cookie-overbroad-domain": TaxonomyIds(cwe_id="CWE-1275"),
    "security/cookies/sec-cookie-overbroad-path": TaxonomyIds(cwe_id="CWE-1275"),
    # ---------------- CORS (Phase 13) ----------------
    "security/cors/sec-cors-wildcard-credentials": TaxonomyIds(cwe_id="CWE-942"),
    "security/cors/sec-cors-reflective-allow-origin": TaxonomyIds(cwe_id="CWE-942"),
    # ---------------- CSRF (Phase 13) ----------------
    "security/csrf/sec-csrf-missing-token": TaxonomyIds(cwe_id="CWE-352"),
    # ---------------- XSS (Phase 13) ----------------
    "security/xss_reflected/sec-xss-reflected": TaxonomyIds(cwe_id="CWE-79"),
    "security/xss_stored/sec-xss-stored": TaxonomyIds(cwe_id="CWE-79"),
    # ---------------- SQLi (Phase 13) ----------------
    "security/sqli/sec-sqli-behavioral": TaxonomyIds(cwe_id="CWE-89"),
    # ---------------- IDOR / BOLA / BFLA ----------------
    "security/idor/sec-idor-cross-user-access": TaxonomyIds(
        cwe_id="CWE-639", owasp_api_id="API-2023-01"
    ),
    "security/api_bola_bfla/sec-bola-cross-tenant-read": TaxonomyIds(
        cwe_id="CWE-639", owasp_api_id="API-2023-01"
    ),
    "security/api_bola_bfla/sec-bfla-elevated-action": TaxonomyIds(
        cwe_id="CWE-863", owasp_api_id="API-2023-03"
    ),
    # ---------------- Frontend secrets / bundle ----------------
    "security/frontend/sec-frontend-secret-in-bundle": TaxonomyIds(cwe_id="CWE-540"),
    "security/frontend/sec-frontend-token-in-storage": TaxonomyIds(cwe_id="CWE-922"),
    "security/frontend/sec-frontend-pii-in-dom": TaxonomyIds(cwe_id="CWE-359"),
    "security/bundle_secrets/sec-bundle-secret-aws": TaxonomyIds(cwe_id="CWE-540"),
    "security/bundle_secrets/sec-bundle-secret-gcp": TaxonomyIds(cwe_id="CWE-540"),
    "security/bundle_secrets/sec-bundle-secret-azure": TaxonomyIds(cwe_id="CWE-540"),
    "security/bundle_secrets/sec-bundle-secret-stripe": TaxonomyIds(cwe_id="CWE-540"),
    "security/bundle_secrets/sec-bundle-secret-github": TaxonomyIds(cwe_id="CWE-540"),
    "security/bundle_secrets/sec-bundle-secret-slack": TaxonomyIds(cwe_id="CWE-540"),
    "security/bundle_secrets/sec-bundle-secret-private-key": TaxonomyIds(cwe_id="CWE-540"),
    # ---------------- Dependencies / SAST (Phase 13) ----------------
    "security/deps/sec-deps-vulnerable": TaxonomyIds(cwe_id="CWE-1104"),
    "security/sast/sec-sast-finding": TaxonomyIds(cwe_id="CWE-693"),
    # ---------------- JWT (Phase 32.01) ----------------
    "security/jwt_weakness/sec-jwt-alg-none": TaxonomyIds(cwe_id="CWE-347", attack_id="T1606.001"),
    "security/jwt_weakness/sec-jwt-weak-hs256-secret": TaxonomyIds(cwe_id="CWE-347"),
    "security/jwt_weakness/sec-jwt-missing-exp": TaxonomyIds(cwe_id="CWE-613"),
    "security/jwt_weakness/sec-jwt-expired": TaxonomyIds(cwe_id="CWE-613"),
    "security/jwt_weakness/sec-jwt-missing-iss-aud": TaxonomyIds(cwe_id="CWE-345"),
    # ---------------- TLS (Phase 32.03) ----------------
    "security/tls_posture/sec-tls-version-legacy": TaxonomyIds(cwe_id="CWE-326", attack_id="T1573"),
    "security/tls_posture/sec-tls-weak-cipher": TaxonomyIds(cwe_id="CWE-326", attack_id="T1573"),
    "security/tls_posture/sec-tls-cert-expired": TaxonomyIds(cwe_id="CWE-295"),
    "security/tls_posture/sec-tls-cert-expiring-soon": TaxonomyIds(cwe_id="CWE-295"),
    "security/tls_posture/sec-tls-hsts-too-short": TaxonomyIds(cwe_id="CWE-319"),
    "security/tls_posture/sec-tls-hsts-missing": TaxonomyIds(cwe_id="CWE-319"),
    # ---------------- GraphQL (Phase 32.04) ----------------
    "security/graphql_safety/sec-graphql-introspection-enabled": TaxonomyIds(cwe_id="CWE-200"),
    "security/graphql_safety/sec-graphql-no-depth-limit": TaxonomyIds(cwe_id="CWE-770"),
    "security/graphql_safety/sec-graphql-no-complexity-limit": TaxonomyIds(cwe_id="CWE-770"),
    "security/graphql_safety/sec-graphql-mutation-no-auth": TaxonomyIds(
        cwe_id="CWE-862", owasp_api_id="API-2023-05"
    ),
    # ---------------- SSRF / open redirect (Phase 32.08) ----------------
    "security/ssrf_redirect/sec-ssrf-suspected": TaxonomyIds(
        cwe_id="CWE-918", owasp_api_id="API-2023-07"
    ),
    "security/ssrf_redirect/sec-open-redirect": TaxonomyIds(cwe_id="CWE-601"),
}


_PREFIX_DEFAULTS: Final[dict[str, TaxonomyIds]] = {
    "security/headers/": TaxonomyIds(cwe_id="CWE-693"),
    "security/cookies/": TaxonomyIds(cwe_id="CWE-1004"),
    "security/cors/": TaxonomyIds(cwe_id="CWE-942"),
    "security/csrf/": TaxonomyIds(cwe_id="CWE-352"),
    "security/xss": TaxonomyIds(cwe_id="CWE-79"),
    "security/sqli/": TaxonomyIds(cwe_id="CWE-89"),
    "security/idor/": TaxonomyIds(cwe_id="CWE-639"),
    "security/frontend/": TaxonomyIds(cwe_id="CWE-540"),
    "security/jwt_weakness/": TaxonomyIds(cwe_id="CWE-347"),
    "security/tls_posture/": TaxonomyIds(cwe_id="CWE-326"),
    "security/graphql_safety/": TaxonomyIds(cwe_id="CWE-770"),
    "security/ssrf_redirect/": TaxonomyIds(cwe_id="CWE-918"),
    "security/bundle_secrets/": TaxonomyIds(cwe_id="CWE-540"),
    "security/api_bola_bfla/": TaxonomyIds(cwe_id="CWE-639", owasp_api_id="API-2023-01"),
}


def lookup(category: str) -> TaxonomyIds:
    """Return the default :class:`TaxonomyIds` for a finding category.

    Exact category match wins; otherwise the longest matching prefix in
    :data:`_PREFIX_DEFAULTS` is returned. Returns an empty
    :class:`TaxonomyIds` (all-None) when nothing matches — the caller
    is responsible for surfacing such gaps to a CWE-mapping CI guard.
    """

    exact = _DEFAULTS.get(category)
    if exact is not None:
        return exact
    best_match: TaxonomyIds = TaxonomyIds()
    best_len = 0
    for prefix, ids in _PREFIX_DEFAULTS.items():
        if category.startswith(prefix) and len(prefix) > best_len:
            best_match = ids
            best_len = len(prefix)
    return best_match


def known_categories() -> tuple[str, ...]:
    """Return every category with an explicit mapping (sorted, stable)."""

    return tuple(sorted(_DEFAULTS))


def known_prefixes() -> tuple[str, ...]:
    """Return every prefix mapping (sorted, stable)."""

    return tuple(sorted(_PREFIX_DEFAULTS))


__all__ = [
    "TaxonomyIds",
    "known_categories",
    "known_prefixes",
    "lookup",
]
