"""Canonical OpenAI Chat Completions provider (Phase 30, ADR-0042).

Calls ``https://api.openai.com/v1/chat/completions`` via ``httpx``. No
``openai`` SDK is imported anywhere in the codebase; the lint guard in
``tests/security/test_no_vendor_sdks.py`` enforces this.

Replaces the per-caller :class:`engine.planner.llm_providers.openai_planner.OpenAiLlmPlanner`
for the canonical surface. The Phase-06 planner facade continues to use
the older class for backwards-compatibility; new consumers use this
adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from engine.llm.budget import estimate_cost_usd
from engine.llm.protocol import LlmRequest
from engine.llm.providers._http_base import HttpLlmProviderBase

# Per-1k-token rates (USD), September-2024 OpenAI list price snapshot.
# Conservative defaults; the user is expected to pin a model that matches
# their negotiated rate.
_PRICING_USD_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
}


@dataclass
class OpenAiProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "openai"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "gpt-4o-mini"
    API_KEY_ENV: ClassVar[str] = "OPENAI_API_KEY"
    ENDPOINT: ClassVar[str] = "https://api.openai.com/v1/chat/completions"

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
            "messages": messages,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "sentinelqa_envelope",
                    "schema": request.response_schema,
                    "strict": True,
                },
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


# Re-export so the cost table is import-stable for the docs site.
PRICING_USD_PER_1K = _PRICING_USD_PER_1K


__all__ = ["OpenAiProvider", "PRICING_USD_PER_1K"]
