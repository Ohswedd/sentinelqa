"""Canonical :class:`LlmProvider` Protocol (, ADR-0042).

Every provider adapter — Anthropic, OpenAI, Gemini, Ollama, Azure OpenAI,
Vertex AI, Mistral, Groq, OpenRouter — implements this single shape. The
caller (planner / analyzer / healer / future) builds an :class:`LlmRequest`,
passes it to ``provider.complete``, and receives an :class:`LlmResponse`
whose ``parsed`` payload has been pre-validated against the request's
``response_schema``.

The Protocol is deliberately small: one ``complete`` call, one
``doctor`` health probe, and class-level ``name`` / ``version`` for the
registry. Caller-specific shape (the planner's proposal envelope, the
analyzer's refinement envelope) is enforced by passing the appropriate
schema into the request — the provider itself stays caller-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Request / Response value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LlmRequest:
    """One LLM call.

    Parameters
    ----------
    system:
    System / instruction message. Almost always a locked prompt loaded
    from the caller's ``llm_prompts/*.md`` tree (, ).
    messages:
    Conversation messages in chronological order. Each message is a
    dict with ``role`` (``"user"`` / ``"assistant"``) and ``content``
    (string). Multi-modal content is out of scope for release.
    response_schema:
    JSON Schema (Draft 2020-12 subset) the response MUST satisfy.
    Required: providers that natively support structured output (most
    do) ask the provider to enforce it; providers that don't fall
    back to client-side validation. Either way the caller can rely on
    :attr:`LlmResponse.parsed` having been validated.
    max_output_tokens:
    Soft upper bound on the response length. Defaults to 1024 — keep
    prompts narrow.
    temperature:
    0.0..1.0. Lower is more deterministic. Tests and CI default to
    ``0.0`` so locked prompts can byte-equal their golden responses.
    caller:
    Which subsystem owns this call. Used for cost attribution and
    audit-log routing.
    run_id:
    The active SentinelQA run-id. Carried through to the audit log so
    a single line can be cross-referenced with the run's audit
    timeline.
    """

    system: str
    messages: tuple[dict[str, str], ...] = ()
    response_schema: dict[str, Any] | None = None
    max_output_tokens: int = 1024
    temperature: float = 0.0
    caller: Literal["planner", "analyzer", "healer", "doctor", "test"] = "planner"
    run_id: str = ""
    # Provider-scoped extras for non-portable knobs (e.g. Gemini's
    # ``safetySettings``). Kept opaque — providers ignore unknown keys.
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LlmResponse:
    """One provider response, post-validation.

    Parameters
    ----------
    text:
    Raw model output text. For structured-output calls this is the
    JSON string before parsing; tests and audit logs use it.
    parsed:
    Pre-validated JSON object. ``None`` only when the response failed
    validation and the caller is expected to fall back. ``available``
    below covers the unreachable-server / missing-model case.
    usage:
    Token accounting for cost computation.
    cost_usd:
    Provider-derived USD cost for THIS call. ``0.0`` for local
    providers (Ollama) and unauthenticated free-tier calls (Groq).
    latency_ms:
    Wall-clock latency of the HTTP round-trip in milliseconds.
    provider:
    The :attr:`LlmProvider.name` that produced this response.
    model:
    The exact model string requested (e.g. ``"claude-3-5-sonnet"``).
    available:
    ``False`` only for graceful-degradation paths (Ollama server
    offline, model not pulled, etc.). On ``False`` the caller is
    expected to fall back to the deterministic path without raising.
    """

    text: str
    parsed: dict[str, Any] | None
    usage: LlmUsage
    cost_usd: float
    latency_ms: float
    provider: str
    model: str
    available: bool = True


# `LlmUsage` is imported lazily below to avoid circular-import pain on
# the engine.llm package's __init__.py.
from engine.llm.budget import LlmUsage  # noqa: E402 (intentional: shared dataclass)

# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Result of an :meth:`LlmProvider.doctor` probe.

    Reachability is best-effort: ``available`` means a 1-token call
    succeeded; ``degraded`` means the provider responded but the model
    rejected the probe (e.g. quota); ``unavailable`` means we couldn't
    reach the provider at all (DNS, network, 5xx).
    """

    provider: str
    model: str
    status: Literal["available", "degraded", "unavailable"]
    latency_ms: float
    detail: str = ""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LlmProvider(Protocol):
    """Every provider adapter must implement this surface."""

    name: ClassVar[str]
    version: ClassVar[str]

    def complete(self, request: LlmRequest) -> LlmResponse:  # pragma: no cover - protocol
        ...

    def doctor(self) -> ProviderHealth:  # pragma: no cover - protocol
        ...


# ---------------------------------------------------------------------------
# Null implementation
# ---------------------------------------------------------------------------


@dataclass
class NullLlmProvider:
    """Default no-op adapter.

    Returns an empty :class:`LlmResponse` with ``available=False``. Cost
    is always ``0.0``. Used when the user has not configured any LLM
    provider; planner / analyzer / healer all fall back to their
    deterministic paths.
    """

    name: ClassVar[str] = "null"
    version: ClassVar[str] = "1.0.0"

    model_label: str = "null"

    def complete(self, request: LlmRequest) -> LlmResponse:
        return LlmResponse(
            text="",
            parsed=None,
            usage=LlmUsage(),
            cost_usd=0.0,
            latency_ms=0.0,
            provider=self.name,
            model=self.model_label,
            available=False,
        )

    def doctor(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            model=self.model_label,
            status="unavailable",
            latency_ms=0.0,
            detail="null provider has no remote endpoint",
        )


__all__ = [
    "LlmProvider",
    "LlmRequest",
    "LlmResponse",
    "LlmUsage",
    "NullLlmProvider",
    "ProviderHealth",
]
