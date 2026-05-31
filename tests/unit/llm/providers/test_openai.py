"""OpenAiProvider (canonical engine.llm) — Chat Completions, Bearer auth."""

from __future__ import annotations

import json

import httpx
import pytest
from engine.errors.base import LlmMissingKeyError
from engine.llm import LlmRequest
from engine.llm.providers.openai import PRICING_USD_PER_1K, OpenAiProvider


def _openai_body(content: str, *, prompt: int = 10, completion: int = 5) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
        "model": "gpt-4o-mini",
    }


def test_openai_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        body = json.loads(req.content.decode("utf-8"))
        assert body["response_format"]["type"] == "json_schema"
        return httpx.Response(200, json=_openai_body('{"ok": true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAiProvider(http_client=client)
    response = provider.complete(
        LlmRequest(
            system="ping",
            response_schema={"type": "object", "required": ["ok"]},
        )
    )
    assert response.available is True
    assert response.parsed == {"ok": True}
    sent = captured[0]
    assert sent.headers["authorization"] == "Bearer sk-test"


def test_openai_cost_uses_pricing_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_openai_body("ok", prompt=1000, completion=1000),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAiProvider(model="gpt-4o-mini", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    rates = PRICING_USD_PER_1K["gpt-4o-mini"]
    expected = rates[0] + rates[1]
    assert response.cost_usd == pytest.approx(expected, rel=1e-3)


def test_openai_unknown_model_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_body("ok"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAiProvider(model="gpt-future-x", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd > 0


def test_openai_401_raises_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "wrong")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(LlmMissingKeyError):
        OpenAiProvider(http_client=client).complete(LlmRequest(system="ping"))


def test_openai_extract_returns_empty_on_no_choices() -> None:
    provider = OpenAiProvider()
    assert provider.extract_response_text({}) == "{}"
    assert provider.extract_response_text({"choices": []}) == "{}"
    assert provider.extract_response_text({"choices": [{"message": {}}]}) == "{}"
    assert provider.extract_response_text({"choices": [{"message": {"content": None}}]}) == "{}"


def test_openai_doctor_uses_base_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_body("ok"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    health = OpenAiProvider(http_client=client).doctor()
    assert health.status == "available"


def test_openai_doctor_unavailable_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    health = OpenAiProvider().doctor()
    assert health.status == "unavailable"
