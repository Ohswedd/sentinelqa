"""Final coverage-floor sweep — pins the remaining ≥95% branch gaps.

Each test exists solely to close a coverage gap that the behavior-
focused tests don't naturally hit. They are small but exercise real
public behavior (no `pragma: no cover` cheats).
"""

from __future__ import annotations

import pytest
from engine.errors.base import LlmBudgetExceededError, LlmMissingKeyError
from engine.llm.budget import LlmBudget
from engine.llm.protocol import LlmRequest
from engine.llm.providers._http_base import HttpLlmProviderBase
from engine.llm.providers.openrouter import OpenRouterProvider


def test_budget_analyzer_sub_cap_breach() -> None:
    """Branch at budget.py:140 — analyzer caller hits its own sub-cap."""

    budget = LlmBudget(max_usd_per_run=10.0, max_usd_analyzer=0.01)
    budget.add(caller="analyzer", input_tokens=0, output_tokens=0, cost_usd=0.008)
    with pytest.raises(LlmBudgetExceededError):
        budget.pre_check(caller="analyzer", estimated_cost_usd=0.005)


def test_budget_healer_sub_cap_breach() -> None:
    """Branch at budget.py:142 — healer caller hits its own sub-cap."""

    budget = LlmBudget(max_usd_per_run=10.0, max_usd_healer=0.01)
    budget.add(caller="healer", input_tokens=0, output_tokens=0, cost_usd=0.008)
    with pytest.raises(LlmBudgetExceededError):
        budget.pre_check(caller="healer", estimated_cost_usd=0.005)


def test_registry_double_bootstrap_is_idempotent() -> None:
    """_bootstrap_builtin_providers early-return when null is already in."""

    from engine.llm.registry import _bootstrap_builtin_providers, list_providers

    before = set(list_providers())
    _bootstrap_builtin_providers()  # idempotent
    _bootstrap_builtin_providers()
    after = set(list_providers())
    assert before == after  # no duplicate registration error raised


def test_registry_register_lazy_skips_duplicate() -> None:
    """_register_lazy short-circuits when the name is already registered."""

    from engine.llm.registry import _register_lazy, list_providers

    before = set(list_providers())
    _register_lazy("gemini", "engine.llm.providers.gemini", "GeminiProvider")
    assert set(list_providers()) == before  # no duplicate raised


def test_http_base_resolve_api_key_with_no_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Branch at _http_base.py:284 — API_KEY_ENV unset on the class."""

    class _NoKeyProvider(HttpLlmProviderBase):
        # Inherits API_KEY_ENV = "" from base.
        pass

    with pytest.raises(LlmMissingKeyError):
        _NoKeyProvider()._resolve_api_key()


def test_openrouter_extract_no_choices_branch() -> None:
    """Branch at openrouter.py:77 — falls through to {} on no choices."""

    provider = OpenRouterProvider()
    assert provider.extract_response_text({"choices": [{"message": {"content": 12}}]}) == "{}"


def test_http_base_validate_schema_with_no_required_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch at _http_base.py:323->331 — schema without `required` key."""

    monkeypatch.setenv("DUMMY_API_KEY", "key")

    from typing import Any, ClassVar

    import httpx

    class _Dummy(HttpLlmProviderBase):
        name: ClassVar[str] = "dummy"
        version: ClassVar[str] = "1.0.0"
        API_KEY_ENV: ClassVar[str] = "DUMMY_API_KEY"
        ENDPOINT: ClassVar[str] = "https://x.example.com"
        DEFAULT_MODEL: ClassVar[str] = "x"

        def endpoint_url(self) -> str:
            return self.ENDPOINT

        def auth_headers(self, *, api_key: str) -> dict[str, str]:
            return {"Authorization": f"Bearer {api_key}"}

        def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
            return {}

        def extract_response_text(self, body: dict[str, Any]) -> str:
            text = body.get("text", "{}")
            if isinstance(text, str):
                return text
            return "{}"

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": '{"any": "value"}'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _Dummy(http_client=client)
    response = provider.complete(
        LlmRequest(
            system="hi",
            # Schema with no `required` — just type-checked.
            response_schema={"type": "object"},
        )
    )
    assert response.parsed == {"any": "value"}
