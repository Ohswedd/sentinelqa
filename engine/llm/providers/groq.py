"""Groq Cloud provider (, ADR-0042).

Calls Groq's OpenAI-compatible endpoint at
``https://api.groq.com/openai/v1/chat/completions`` via ``httpx``. No
``groq`` SDK is imported. Groq's headline value is latency; the
:class:`engine.llm.protocol.LlmResponse` ``latency_ms`` field captures
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from engine.llm.budget import estimate_cost_usd
from engine.llm.protocol import LlmRequest
from engine.llm.providers._http_base import HttpLlmProviderBase

_PRICING_USD_PER_1K: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.00059, 0.00079),
    "llama-3.1-8b-instant": (0.00005, 0.00008),
    "mixtral-8x7b-32768": (0.00024, 0.00024),
}


@dataclass
class GroqProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "groq"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "llama-3.1-8b-instant"
    API_KEY_ENV: ClassVar[str] = "GROQ_API_KEY"
    ENDPOINT: ClassVar[str] = "https://api.groq.com/openai/v1/chat/completions"

    def endpoint_url(self) -> str:
        return self.ENDPOINT

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for msg in request.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages or [{"role": "user", "content": "ping"}],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_object",
            }
        return payload

    def extract_response_text(self, body: dict[str, Any]) -> str:
        choices = body.get("choices") or []
        if not choices:
            return "{}"
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        return "{}"

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        usage = body.get("usage") or {}
        return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))

    def cost_from_response(
        self,
        *,
        body: dict[str, Any],
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        rates = _PRICING_USD_PER_1K.get(model)
        if rates is None:
            return estimate_cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)
        in_rate, out_rate = rates
        return estimate_cost_usd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            price_per_1k_input=in_rate,
            price_per_1k_output=out_rate,
        )


PRICING_USD_PER_1K = _PRICING_USD_PER_1K


__all__ = ["GroqProvider", "PRICING_USD_PER_1K"]
