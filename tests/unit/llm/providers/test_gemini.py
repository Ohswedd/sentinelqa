"""GeminiProvider — mocked happy path + error grid."""

from __future__ import annotations

import json

import httpx
import pytest
from engine.errors.base import (
    LlmMissingKeyError,
    LlmRateLimitedError,
    LlmRequestRejectedError,
    LlmResponseValidationError,
)
from engine.llm import LlmBudget, LlmRequest
from engine.llm.providers.gemini import GeminiProvider


def _gemini_body(text: str, *, prompt_tokens: int = 10, response_tokens: int = 5) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {
            "promptTokenCount": prompt_tokens,
            "candidatesTokenCount": response_tokens,
        },
    }


def test_gemini_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        body = json.loads(req.content.decode("utf-8"))
        # responseSchema travels through the generation config block.
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(200, json=_gemini_body('{"ok": true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GeminiProvider(model="gemini-1.5-flash", http_client=client)
    response = provider.complete(
        LlmRequest(
            system="ping",
            messages=({"role": "user", "content": "hi"},),
            response_schema={"type": "object", "required": ["ok"]},
            max_output_tokens=10,
        )
    )
    assert response.available is True
    assert response.parsed == {"ok": True}
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5
    # 10 in / 5 out at gemini-1.5-flash rates = tiny but > 0.
    assert response.cost_usd > 0
    assert response.cost_usd < 0.001
    # Header carried the api key.
    sent = captured[0]
    assert sent.headers["x-goog-api-key"] == "test-key"


def test_gemini_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider()
    with pytest.raises(LlmMissingKeyError):
        provider.complete(LlmRequest(system="ping"))


def test_gemini_429_raises_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limit"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GeminiProvider(http_client=client)
    with pytest.raises(LlmRateLimitedError):
        provider.complete(LlmRequest(system="ping"))


def test_gemini_500_raises_request_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GeminiProvider(http_client=client)
    with pytest.raises(LlmRequestRejectedError):
        provider.complete(LlmRequest(system="ping"))


def test_gemini_schema_validation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_body("{}"))  # missing required key

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GeminiProvider(http_client=client)
    with pytest.raises(LlmResponseValidationError):
        provider.complete(
            LlmRequest(
                system="",
                response_schema={"type": "object", "required": ["flows"]},
            )
        )


def test_gemini_budget_exceeded_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    budget = LlmBudget(max_usd_per_run=0.000001)  # essentially zero

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_body('{"ok":true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GeminiProvider(http_client=client, budget=budget)
    from engine.errors.base import LlmBudgetExceededError

    with pytest.raises(LlmBudgetExceededError):
        provider.complete(LlmRequest(system="long prompt" * 200, max_output_tokens=1000))


def test_gemini_doctor_available_when_endpoint_responds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_body("ok"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GeminiProvider(http_client=client)
    health = provider.doctor()
    assert health.status == "available"


def test_gemini_doctor_unavailable_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    health = GeminiProvider().doctor()
    assert health.status == "unavailable"
    assert "GEMINI_API_KEY" in health.detail
