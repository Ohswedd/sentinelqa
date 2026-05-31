"""OllamaProvider — local provider with graceful offline fallback."""

from __future__ import annotations

import httpx
from engine.llm import LlmRequest
from engine.llm.providers.ollama import OllamaProvider


def _ollama_chat_body(content: str, *, prompt: int = 10, eval_count: int = 5) -> dict:
    return {
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": prompt,
        "eval_count": eval_count,
    }


def test_ollama_happy_path() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert "key" not in str(req.headers).lower() or "x-goog" not in str(req.headers).lower()
        return httpx.Response(200, json=_ollama_chat_body('{"ok": true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(http_client=client)
    response = provider.complete(
        LlmRequest(system="ping", messages=({"role": "user", "content": "hi"},))
    )
    assert response.available is True
    assert response.cost_usd == 0.0  # local always free
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5


def test_ollama_unreachable_returns_available_false() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(http_client=client)
    response = provider.complete(LlmRequest(system="ping"))
    assert response.available is False
    assert response.cost_usd == 0.0


def test_ollama_missing_model_returns_available_false() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'foo' not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(model="foo", http_client=client)
    response = provider.complete(LlmRequest(system="ping"))
    assert response.available is False


def test_ollama_structured_output_validation_returns_unparsed_but_available() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ollama_chat_body('"not an object"'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(http_client=client)
    response = provider.complete(
        LlmRequest(
            system="ping",
            response_schema={"type": "object", "required": ["x"]},
        )
    )
    assert response.available is True
    assert response.parsed is None  # validation failed but the response is still surfaced


def test_ollama_doctor_lists_installed_models_when_model_present() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen2.5-coder:7b"}, {"name": "llama3"}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(http_client=client)
    health = provider.doctor()
    assert health.status == "available"
    assert "2 model" in health.detail


def test_ollama_doctor_degraded_when_model_not_installed() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(http_client=client, model="qwen2.5-coder:7b")
    health = provider.doctor()
    assert health.status == "degraded"
    assert "ollama pull" in health.detail


def test_ollama_doctor_unavailable_when_unreachable() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(http_client=client)
    health = provider.doctor()
    assert health.status == "unavailable"
