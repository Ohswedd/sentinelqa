"""GroqProvider — OpenAI-compatible, latency-forward."""

from __future__ import annotations

import httpx
import pytest
from engine.errors.base import LlmMissingKeyError, LlmRateLimitedError
from engine.llm import LlmRequest
from engine.llm.providers.groq import GroqProvider


def _groq_body(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_groq_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer groq-test"
        return httpx.Response(200, json=_groq_body("hello"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqProvider(http_client=client)
    response = provider.complete(LlmRequest(system="ping"))
    assert response.available is True
    # latency_ms is populated.
    assert response.latency_ms >= 0


def test_groq_401_raises_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "wrong")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqProvider(http_client=client)
    with pytest.raises(LlmMissingKeyError):
        provider.complete(LlmRequest(system="ping"))


def test_groq_429_raises_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqProvider(http_client=client)
    with pytest.raises(LlmRateLimitedError):
        provider.complete(LlmRequest(system="ping"))


def test_groq_cost_uses_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqProvider(model="llama-3.1-8b-instant", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    # llama-3.1-8b-instant: 0.00005 in + 0.00008 out per 1k tokens
    assert response.cost_usd == pytest.approx(0.00013, rel=1e-3)
