"""Concrete provider adapters (Phase 30, ADR-0042).

Importing this package registers the built-in null provider plus the
nine Phase-30 lazy factories. Concrete adapter modules are only loaded
when their name resolves through :func:`engine.llm.registry.resolve_provider`,
so heavyweight imports (httpx, JWT crypto) stay off the cold CLI path.
"""

from __future__ import annotations

from engine.llm.registry import _bootstrap_builtin_providers, _register_lazy


def _bootstrap() -> None:
    _bootstrap_builtin_providers()
    _register_lazy(
        "anthropic",
        "engine.llm.providers.anthropic",
        "AnthropicProvider",
    )
    _register_lazy(
        "openai",
        "engine.llm.providers.openai",
        "OpenAiProvider",
    )
    _register_lazy(
        "gemini",
        "engine.llm.providers.gemini",
        "GeminiProvider",
    )
    _register_lazy(
        "ollama",
        "engine.llm.providers.ollama",
        "OllamaProvider",
    )
    _register_lazy(
        "azure_openai",
        "engine.llm.providers.azure_openai",
        "AzureOpenAiProvider",
    )
    _register_lazy(
        "vertex",
        "engine.llm.providers.vertex",
        "VertexAiProvider",
    )
    _register_lazy(
        "mistral",
        "engine.llm.providers.mistral",
        "MistralProvider",
    )
    _register_lazy(
        "groq",
        "engine.llm.providers.groq",
        "GroqProvider",
    )
    _register_lazy(
        "openrouter",
        "engine.llm.providers.openrouter",
        "OpenRouterProvider",
    )


_bootstrap()


__all__: list[str] = []
