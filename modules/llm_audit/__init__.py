"""LLM-Code audit module (Phase 19, PRD §10.9, CLAUDE.md §9, §31).

Importing this package wires :class:`LlmAuditModule` into the default
orchestrator registry so ``sentinel llm-audit`` and ``sentinel audit``
both pick it up automatically.

The module hunts for the failure modes characteristic of LLM-generated
applications: dead buttons, fake routes, mock data shipped to
production, forms without working submit, missing CRUD edges, UI-only
auth gates, hardcoded credentials, secrets in browser storage, missing
loading / error states, frontend / backend validation mismatch,
"coming soon" placeholders, and console errors the UI silently
ignores. Each check has a stable ``LLM-*`` rule ID owned by
``modules.llm_audit.rules`` and produces typed :class:`Finding`
records with PRD §20 evidence.

ADR-0024 documents the rule catalogue, severity policy, and the
deliberate decision to consume already-captured signals (discovery
output, runner artifacts) rather than spawning a parallel browser
session.
"""

from __future__ import annotations

from modules.llm_audit.module import (
    LlmAuditModule,
    LlmAuditModuleOptions,
    register_with_default_registry,
)

register_with_default_registry()


__all__ = [
    "LlmAuditModule",
    "LlmAuditModuleOptions",
    "register_with_default_registry",
]
