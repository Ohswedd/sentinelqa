"""Shape + runtime-checkable contract for :class:`engine.llm.LlmProvider`.

The Protocol is the public surface every adapter must satisfy. We check
``isinstance(provider, LlmProvider)`` at runtime, the class-level
``name`` and ``version`` attributes, and the method signatures of
``complete()`` / ``doctor()``.
"""

from __future__ import annotations

from engine.llm import (
    LlmProvider,
    LlmRequest,
    LlmResponse,
    LlmUsage,
    NullLlmProvider,
    ProviderHealth,
    list_providers,
    resolve_provider,
)


def test_null_provider_satisfies_protocol() -> None:
    provider = NullLlmProvider()
    assert isinstance(provider, LlmProvider)
    assert provider.name == "null"
    assert provider.version == "1.0.0"


def test_null_provider_complete_returns_unavailable() -> None:
    provider = NullLlmProvider()
    request = LlmRequest(system="locked prompt", messages=())
    response = provider.complete(request)
    assert isinstance(response, LlmResponse)
    assert response.available is False
    assert response.cost_usd == 0.0
    assert response.usage == LlmUsage()
    assert response.provider == "null"


def test_null_provider_doctor_reports_unavailable() -> None:
    health = NullLlmProvider().doctor()
    assert isinstance(health, ProviderHealth)
    assert health.status == "unavailable"


def test_registry_lists_every_provider() -> None:
    names = list_providers()
    # Ten total: 2 carried over (anthropic + openai) + 7 new + 1 null.
    expected = {
        "null",
        "anthropic",
        "openai",
        "gemini",
        "ollama",
        "azure_openai",
        "vertex",
        "mistral",
        "groq",
        "openrouter",
    }
    assert set(names) == expected
    # Sorted.
    assert names == tuple(sorted(names))


def test_resolve_each_registered_provider() -> None:
    for name in list_providers():
        provider = resolve_provider(name)
        assert isinstance(provider, LlmProvider), name
        assert provider.name == name
