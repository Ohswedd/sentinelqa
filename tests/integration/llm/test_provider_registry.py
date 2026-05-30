"""Provider registry — registration, resolution, duplicate guards."""

from __future__ import annotations

import pytest
from engine.llm import (
    LlmProvider,
    LlmRequest,
    LlmResponse,
    ProviderAlreadyRegisteredError,
    ProviderHealth,
    ProviderNotFoundError,
    list_providers,
    register_provider,
    reset_registry,
    resolve_provider,
)
from engine.llm.budget import LlmUsage


@pytest.fixture(autouse=True)
def _restore_registry() -> None:
    """Snapshot the registry around each test so we don't break others."""

    saved = list_providers()
    yield
    reset_registry()
    # Re-import providers to re-populate the canonical registry.
    import importlib

    import engine.llm.providers as _providers

    importlib.reload(_providers)
    assert set(list_providers()) >= set(saved)


class _FakeProvider:
    name: str = "fake"
    version: str = "0.0.1"

    def complete(self, request: LlmRequest) -> LlmResponse:
        return LlmResponse(
            text="",
            parsed=None,
            usage=LlmUsage(),
            cost_usd=0.0,
            latency_ms=0.0,
            provider=self.name,
            model="fake-1",
            available=False,
        )

    def doctor(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            model="fake-1",
            status="unavailable",
            latency_ms=0.0,
        )


def test_register_then_resolve() -> None:
    register_provider("fake", _FakeProvider)
    provider = resolve_provider("fake")
    assert isinstance(provider, LlmProvider)
    assert provider.name == "fake"


def test_register_duplicate_raises() -> None:
    register_provider("dup", _FakeProvider)
    with pytest.raises(ProviderAlreadyRegisteredError):
        register_provider("dup", _FakeProvider)


def test_resolve_unknown_raises() -> None:
    with pytest.raises(ProviderNotFoundError):
        resolve_provider("does-not-exist")


def test_register_empty_name_rejected() -> None:
    with pytest.raises(ValueError):
        register_provider("  ", _FakeProvider)


def test_register_is_case_insensitive() -> None:
    register_provider("Mixed", _FakeProvider)
    # Resolved by lowercase key.
    assert resolve_provider("mixed").name == "fake"


def test_reset_registry_clears() -> None:
    register_provider("temp", _FakeProvider)
    reset_registry()
    assert list_providers() == ()
