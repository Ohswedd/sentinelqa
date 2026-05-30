"""MistralProvider — bearer + json_schema response_format."""

from __future__ import annotations

import json

import httpx
import pytest
from engine.errors.base import LlmMissingKeyError, LlmResponseValidationError
from engine.llm import LlmRequest
from engine.llm.providers.mistral import MistralProvider


def _mistral_body(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 3},
    }


def test_mistral_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test")
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        body = json.loads(req.content.decode("utf-8"))
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(200, json=_mistral_body('{"ok": true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = MistralProvider(http_client=client)
    response = provider.complete(
        LlmRequest(
            system="ping",
            response_schema={"type": "object", "required": ["ok"]},
        )
    )
    assert response.available is True
    assert response.parsed == {"ok": True}
    sent = captured[0]
    assert sent.headers["authorization"] == "Bearer mistral-test"


def test_mistral_401_raises_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "wrong")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = MistralProvider(http_client=client)
    with pytest.raises(LlmMissingKeyError):
        provider.complete(LlmRequest(system="ping"))


def test_mistral_structured_output_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "m")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mistral_body("not json"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = MistralProvider(http_client=client)
    with pytest.raises(LlmResponseValidationError):
        provider.complete(
            LlmRequest(
                system="",
                response_schema={"type": "object"},
            )
        )


def test_mistral_cost_uses_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "m")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = MistralProvider(model="mistral-small-latest", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    # mistral-small-latest: 0.0002 in + 0.0006 out per 1k tokens = 0.0008
    assert response.cost_usd == pytest.approx(0.0008, rel=1e-6)
