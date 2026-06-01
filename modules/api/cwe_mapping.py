"""Default CWE / ATT&CK / OWASP-API mapping for API findings.

 / ADR-0044. The API module emits findings in categories of
the form ``api/<check>/<rule_id_lower>``. This table maps those
categories to canonical taxonomy ids so SARIF / dashboard consumers can
deep-link.
"""

from __future__ import annotations

from typing import Final

from modules.security.cwe_mapping import TaxonomyIds

_DEFAULTS: Final[dict[str, TaxonomyIds]] = {
    "api/contract/api-contract-schema-violation": TaxonomyIds(cwe_id="CWE-20"),
    "api/contract/api-contract-status-mismatch": TaxonomyIds(cwe_id="CWE-20"),
    "api/contract/api-contract-missing-content-type": TaxonomyIds(cwe_id="CWE-693"),
    "api/auth/api-auth-missing": TaxonomyIds(cwe_id="CWE-862", owasp_api_id="API-2023-02"),
    "api/auth/api-auth-broken": TaxonomyIds(cwe_id="CWE-287", owasp_api_id="API-2023-02"),
    "api/auth/api-auth-token-leak": TaxonomyIds(cwe_id="CWE-522"),
    "api/latency/api-latency-budget-exceeded": TaxonomyIds(cwe_id="CWE-400"),
    "api/negative/api-negative-no-validation": TaxonomyIds(cwe_id="CWE-20"),
    "api/negative/api-negative-server-error": TaxonomyIds(cwe_id="CWE-754"),
}


_PREFIX_DEFAULTS: Final[dict[str, TaxonomyIds]] = {
    "api/contract/": TaxonomyIds(cwe_id="CWE-20"),
    "api/auth/": TaxonomyIds(cwe_id="CWE-287", owasp_api_id="API-2023-02"),
    "api/latency/": TaxonomyIds(cwe_id="CWE-400"),
    "api/negative/": TaxonomyIds(cwe_id="CWE-20"),
}


def lookup(category: str) -> TaxonomyIds:
    """Return the default :class:`TaxonomyIds` for an API finding category."""

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
    return tuple(sorted(_DEFAULTS))


__all__ = ["known_categories", "lookup"]
