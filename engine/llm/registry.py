"""Provider registry (, ADR-0042).

A tiny in-process registry mapping ``provider.name`` to a factory
``Callable[[], LlmProvider]``. The lazy-callable shape keeps every
provider's heavy imports (httpx client, cost table) off the critical
``import sentinel_cli`` path; providers are only constructed when their
name resolves through ``resolve_provider``.

Tests can :func:`reset_registry` to start clean. The CLI's
``sentinel llm list`` consumes :func:`list_providers`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from engine.llm.protocol import LlmProvider

ProviderFactory = Callable[[], "LlmProvider"]


class ProviderAlreadyRegisteredError(KeyError):
    """A provider with this name is already registered."""


class ProviderNotFoundError(LookupError):
    """No provider is registered under this name."""


_REGISTRY: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register ``factory`` under ``name``.

    Raises :class:`ProviderAlreadyRegisteredError` on a duplicate; the
    caller can :func:`reset_registry` first if they intend to override.
    """

    key = name.strip().lower()
    if not key:
        raise ValueError("Provider name must be a non-empty string.")
    if key in _REGISTRY:
        raise ProviderAlreadyRegisteredError(key)
    _REGISTRY[key] = factory


def resolve_provider(name: str) -> LlmProvider:
    """Resolve a provider by name.

    Raises :class:`ProviderNotFoundError` when no factory is registered.
    The factory is called fresh on each resolve; providers are cheap to
    construct (lazy httpx client, no auth probe at construction time).
    """

    key = name.strip().lower()
    factory = _REGISTRY.get(key)
    if factory is None:
        raise ProviderNotFoundError(key)
    return factory()


def list_providers() -> tuple[str, ...]:
    """Return the registered provider names sorted alphabetically."""

    return tuple(sorted(_REGISTRY))


def reset_registry() -> None:
    """Clear every registered factory. Test-only."""

    _REGISTRY.clear()


def _bootstrap_builtin_providers() -> None:
    """Register the always-available providers.

    Called by :mod:`engine.llm.providers` at import time so the registry
    is populated even before any caller asks for a specific provider.
    Concrete provider modules are imported lazily — only when their name
    is resolved — so this stays fast on the cold ``sentinel --version``
    path.
    """

    if "null" in _REGISTRY:
        return

    def _null() -> LlmProvider:
        from engine.llm.protocol import NullLlmProvider

        return NullLlmProvider()

    _REGISTRY["null"] = _null


def _register_lazy(name: str, dotted: str, cls: str) -> None:
    """Helper: register a provider by dotted module path + class name."""

    def factory() -> LlmProvider:
        import importlib

        from engine.llm.protocol import LlmProvider as _LlmProvider

        mod = importlib.import_module(dotted)
        instance = getattr(mod, cls)()
        assert isinstance(instance, _LlmProvider), f"{dotted}.{cls} does not implement LlmProvider"
        return instance

    key = name.strip().lower()
    if key in _REGISTRY:
        return
    _REGISTRY[key] = factory


__all__ = [
    "ProviderAlreadyRegisteredError",
    "ProviderFactory",
    "ProviderNotFoundError",
    "list_providers",
    "register_provider",
    "reset_registry",
    "resolve_provider",
]
