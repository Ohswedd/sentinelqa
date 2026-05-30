"""OpenRouterProvider — gateway with usage.cost passthrough."""

from __future__ import annotations

import httpx
import pytest
from engine.errors.base import LlmMissingKeyError, LlmRequestRejectedError
from engine.llm import LlmRequest
from engine.llm.providers.openrouter import OpenRouterProvider


def test_openrouter_happy_path_with_provider_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok":true}'}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cost": 0.00125,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(http_client=client)
    response = provider.complete(LlmRequest(system="ping"))
    assert response.available is True
    # Cost trusted verbatim — NOT recomputed.
    assert response.cost_usd == pytest.approx(0.00125)
    sent = captured[0]
    # Polite identification headers.
    assert sent.headers["http-referer"] == "https://github.com/Ohswedd/sentinelqa"
    assert sent.headers["x-title"] == "SentinelQA"


def test_openrouter_falls_back_to_token_estimate_when_no_usage_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(http_client=client)
    response = provider.complete(LlmRequest(system=""))
    # Falls back to default rate estimate (0.003 + 0.015 = 0.018 per 1k+1k).
    assert response.cost_usd > 0


def test_openrouter_401_raises_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "wrong")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(http_client=client)
    with pytest.raises(LlmMissingKeyError):
        provider.complete(LlmRequest(system="ping"))


def test_openrouter_404_model_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(model="bad/model", http_client=client)
    with pytest.raises(LlmRequestRejectedError):
        provider.complete(LlmRequest(system="ping"))
