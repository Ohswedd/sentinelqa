"""Canonical Anthropic Messages provider (Phase 30, ADR-0042).

Calls ``https://api.anthropic.com/v1/messages`` via ``httpx``. No
``anthropic`` SDK is imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from engine.llm.budget import estimate_cost_usd
from engine.llm.protocol import LlmRequest
from engine.llm.providers._http_base import HttpLlmProviderBase

# Per-1k-token rates (USD). Anthropic public list-price snapshot.
_PRICING_USD_PER_1K: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-5-haiku-20241022": (0.0008, 0.004),
    "claude-3-opus-20240229": (0.015, 0.075),
}


@dataclass
class AnthropicProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "anthropic"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "claude-3-5-sonnet-20241022"
    API_KEY_ENV: ClassVar[str] = "ANTHROPIC_API_KEY"
    ENDPOINT: ClassVar[str] = "https://api.anthropic.com/v1/messages"
    API_VERSION: ClassVar[str] = "2023-06-01"

    def endpoint_url(self) -> str:
        return self.ENDPOINT

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

    def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        for msg in request.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "messages": messages or [{"role": "user", "content": "ping"}],
        }
        if request.system:
            payload["system"] = request.system
        # Anthropic doesn't have a native structured-output flag; we rely
        # on the locked prompt's "respond with JSON only" instruction and
        # client-side validation.
        return payload

    def extract_response_text(self, body: dict[str, Any]) -> str:
        blocks = body.get("content") or []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    return text
        return "{}"

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        usage = body.get("usage") or {}
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))

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


__all__ = ["AnthropicProvider", "PRICING_USD_PER_1K"]
