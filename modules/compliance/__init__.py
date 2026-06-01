"""Compliance Packs module (, ADR-0046).

Ships deterministic compliance-regime checks alongside SentinelQA's
existing modules. The four sub-packs that land in are:

- ``wcag-2.2-aa`` — wires the accessibility module's axe-core
 WCAG 2.2 tags plus the deterministic SCs in
 :mod:`modules.accessibility.checks.wcag22`.
- ``gdpr-baseline`` — :mod:`modules.compliance.gdpr` (cookie consent,
 cookies-before-consent, asymmetric reject UX).
- ``ccpa-baseline`` — :mod:`modules.compliance.ccpa` (Do Not Sell link
 presence + opt-out form verification).
- ``soc2-trail`` — :mod:`modules.compliance.soc2_trail` (7-gate audit
 on SentinelQA's own ``audit.log``).

our engineering rules wording rule is load-bearing: every finding says
"Automated <regime> check found …" rather than claiming the target
is *compliant*. The forbidden-phrase guard in
``tests/security/test_no_compliance_claims.py`` enforces this for the
compliance module sources.
"""

from __future__ import annotations

from modules.compliance.module import (
    COMPLIANCE_SCHEMA_VERSION,
    ComplianceModule,
    ComplianceModuleOptions,
    register_with_default_registry,
)

register_with_default_registry()


__all__ = [
    "COMPLIANCE_SCHEMA_VERSION",
    "ComplianceModule",
    "ComplianceModuleOptions",
    "register_with_default_registry",
]
