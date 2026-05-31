"""Canonical multi-provider LLM adapter surface (Phase 30, ADR-0042).

Every LLM-augmented module (planner, analyzer, healer, future) consumes
its model behind the :class:`LlmProvider` Protocol defined here. The
existing per-caller protocols (:class:`engine.planner.llm_adapter.LlmPlanner`,
:class:`engine.analyzer.llm_explainer.LlmExplainer`) remain as thin facades
that wrap a canonical provider for their caller-specific call sites.

Hard constraints (CLAUDE.md §35, §6, §33):

- HTTP-only via :mod:`httpx`. No vendor SDKs are imported, anywhere, ever.
- The user brings their own credentials (env-var only, never inlined).
- Every outgoing request body and incoming response body is redacted via
  :mod:`engine.policy.redaction` before it touches a log line or audit
  entry. Locked prompts live in the caller's package (Phase 06 / 09); the
  provider is opaque to prompt text.
- Per-run cost is bounded by :class:`engine.llm.budget.LlmBudget`. Each
  outbound call calls ``budget.pre_check(estimate)`` before sending and
  ``budget.add(actual)`` on completion. On overrun, the caller falls back
  to the deterministic path; the run still completes.
- Per-provider rate-limit is enforced by
  :class:`engine.llm.rate_limit.RateLimiter`; the bucket lives on the
  registry so all consumers share it.
"""

from __future__ import annotations

# Populate the registry with the 9 lazy provider factories. Each entry
# is just a Callable[[], LlmProvider]; the concrete provider modules are
# imported only when ``resolve_provider`` is called for a given name.
from engine.llm import providers as _providers  # noqa: F401  — import for side-effects
from engine.llm.budget import (
    LlmBudget,
    LlmUsage,
    estimate_cost_usd,
)

# Re-import LlmProvider last so its Protocol shape lives next to the
# helpers it composes. The Protocol is `@runtime_checkable` so
# `isinstance(obj, LlmProvider)` works in CLI inspections.
from engine.llm.protocol import (
    LlmProvider,
    LlmRequest,
    LlmResponse,
    NullLlmProvider,
    ProviderHealth,
)
from engine.llm.rate_limit import LlmRateLimit, TokenBucket
from engine.llm.redaction import LlmRedactionPolicy, redact_request, redact_response
from engine.llm.registry import (
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
    list_providers,
    register_provider,
    reset_registry,
    resolve_provider,
)

__all__ = [
    "LlmBudget",
    "LlmProvider",
    "LlmRateLimit",
    "LlmRedactionPolicy",
    "LlmRequest",
    "LlmResponse",
    "LlmUsage",
    "NullLlmProvider",
    "ProviderAlreadyRegisteredError",
    "ProviderHealth",
    "ProviderNotFoundError",
    "TokenBucket",
    "estimate_cost_usd",
    "list_providers",
    "redact_request",
    "redact_response",
    "register_provider",
    "reset_registry",
    "resolve_provider",
]
