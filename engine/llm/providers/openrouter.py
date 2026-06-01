"""OpenRouter (gateway) provider (, ADR-0042).

Calls OpenRouter's OpenAI-compatible endpoint at
``https://openrouter.ai/api/v1/chat/completions`` via ``httpx``. No
``openrouter`` SDK is imported (none exists publicly; the surface is
REST).

OpenRouter is a *gateway* that routes calls to many underlying models
(Anthropic / Google / Meta / etc.). The model field is namespaced:
``anthropic/claude-3.5-sonnet``, ``meta-llama/llama-3.1-70b-instruct``,
…

Cost is OpenRouter-driven: every response includes its computed cost on
the ``usage.cost`` field (USD). The adapter trusts that value rather
than re-deriving from a per-model table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from engine.llm.budget import estimate_cost_usd
from engine.llm.protocol import LlmRequest
from engine.llm.providers._http_base import HttpLlmProviderBase


@dataclass
class OpenRouterProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "openrouter"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "anthropic/claude-3.5-sonnet"
    API_KEY_ENV: ClassVar[str] = "OPENROUTER_API_KEY"
    ENDPOINT: ClassVar[str] = "https://openrouter.ai/api/v1/chat/completions"
    HTTP_REFERER: ClassVar[str] = "https://github.com/Ohswedd/sentinelqa"
    X_TITLE: ClassVar[str] = "SentinelQA"

    def endpoint_url(self) -> str:
        return self.ENDPOINT

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        # The polite-identification headers OpenRouter recommends so the
        # gateway can attribute calls; they DO NOT leak secrets.
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.HTTP_REFERER,
            "X-Title": self.X_TITLE,
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
        usage = body.get("usage") or {}
        provider_cost = usage.get("cost")
        if isinstance(provider_cost, int | float) and provider_cost >= 0:
            return float(provider_cost)
        # Fall back to a conservative token estimate when OpenRouter
        # didn't return a usage.cost (older API versions, free models).
        return estimate_cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)


__all__ = ["OpenRouterProvider"]
