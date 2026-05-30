"""AnthropicProvider — Messages endpoint, x-api-key header."""

from __future__ import annotations

import httpx
import pytest
from engine.errors.base import LlmMissingKeyError, LlmRequestRejectedError
from engine.llm import LlmRequest
from engine.llm.providers.anthropic import PRICING_USD_PER_1K, AnthropicProvider


def _anthropic_body(text: str, *, in_tok: int = 10, out_tok: int = 5) -> dict:
    return {
        "id": "msg_01",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-3-5-sonnet-20241022",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
    }


def test_anthropic_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json=_anthropic_body('{"ok": true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AnthropicProvider(http_client=client)
    response = provider.complete(LlmRequest(system="ping"))
    assert response.available is True
    sent = captured[0]
    # Anthropic uses x-api-key (NOT Bearer).
    assert sent.headers["x-api-key"] == "ant-test"
    assert sent.headers["anthropic-version"] == "2023-06-01"


def test_anthropic_cost_uses_pricing_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_anthropic_body("ok", in_tok=1000, out_tok=1000),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AnthropicProvider(model="claude-3-5-haiku-20241022", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    # claude-3-5-haiku-20241022: 0.0008 in + 0.004 out per 1k tokens = 0.0048
    expected = PRICING_USD_PER_1K["claude-3-5-haiku-20241022"]
    expected_cost = expected[0] + expected[1]
    assert response.cost_usd == pytest.approx(expected_cost, rel=1e-3)


def test_anthropic_unknown_model_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_anthropic_body("ok"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AnthropicProvider(model="claude-future-unknown", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd > 0


def test_anthropic_401_raises_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "wrong")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(LlmMissingKeyError):
        AnthropicProvider(http_client=client).complete(LlmRequest(system="ping"))


def test_anthropic_5xx_raises_request_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(LlmRequestRejectedError):
        AnthropicProvider(http_client=client).complete(LlmRequest(system="ping"))


def test_anthropic_extract_returns_empty_object_on_no_content() -> None:
    provider = AnthropicProvider()
    # The provider always returns "{}" when there is no text block.
    assert provider.extract_response_text({}) == "{}"
    assert provider.extract_response_text({"content": []}) == "{}"
    assert provider.extract_response_text({"content": [{"type": "tool_use"}]}) == "{}"
