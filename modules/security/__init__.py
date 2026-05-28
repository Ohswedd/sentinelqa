"""Safe Security audit module (Phase 13, PRD §10.7, ADR-0018).

Importing this package wires :class:`SecurityModule` into the default
orchestrator registry so ``sentinel security`` and ``sentinel audit``
both pick it up automatically.

The module exercises PRD §10.7 capabilities: response-header hygiene,
cookie flags, CORS/CSRF, reflected XSS, SQLi (sandbox-gated), IDOR
smoke, frontend-secret leakage, and dependency / SAST scanners. Per
CLAUDE.md §6 + §26 every probe goes through :func:`SafetyPolicy.enforce`
before the first network request, and dangerous probes (stored XSS,
SQLi) require ``security.mode == "authorized_destructive"`` plus a
valid proof-of-authorization document.

No stealth, evasion, fingerprint-spoofing, or bypass paths exist in
this module (and the AST guard in
``tests/security/test_module_calls_policy.py`` keeps them from sneaking
in).
"""

from __future__ import annotations

from modules.security.module import (
    SecurityModule,
    SecurityModuleOptions,
    register_with_default_registry,
)

register_with_default_registry()


__all__ = [
    "SecurityModule",
    "SecurityModuleOptions",
    "register_with_default_registry",
]
