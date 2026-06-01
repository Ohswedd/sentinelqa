"""Azure OpenAI provider (, ADR-0042).

Calls
``https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=<apiver>``
via ``httpx``. No ``openai`` SDK is imported.

The Azure URL triple ``(resource, deployment, api_version)`` is config-
driven via :class:`engine.config.schema.LlmProviderAzureConfig`. Callers
construct the provider with these three values; tests pass them in
directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from engine.llm.budget import estimate_cost_usd
from engine.llm.protocol import LlmRequest
from engine.llm.providers._http_base import HttpLlmProviderBase

# Azure publishes per-deployment pricing; SentinelQA defaults to the
# global list-price tier. Users can override via the cost-mapping API
# in the future.
_PRICING_USD_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-35-turbo": (0.0005, 0.0015),
}


@dataclass
class AzureOpenAiProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "azure_openai"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "gpt-4o-mini"
    API_KEY_ENV: ClassVar[str] = "AZURE_OPENAI_API_KEY"

    resource: str = ""
    deployment: str = ""
    api_version: str = "2024-08-01-preview"

    def endpoint_url(self) -> str:
        if not self.resource or not self.deployment:
            raise ValueError(
                "AzureOpenAiProvider requires `resource` and `deployment` "
                "to be configured before calling the endpoint."
            )
        return (
            f"https://{self.resource}.openai.azure.com/openai/deployments/"
            f"{self.deployment}/chat/completions?api-version={self.api_version}"
        )

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        # Azure uses `api-key:` (NOT `Authorization: Bearer`).
        return {
            "api-key": api_key,
            "Content-Type": "application/json",
        }

    def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for msg in request.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        payload: dict[str, Any] = {
            # Azure ignores `model` (deployment is the URL path), but
            # OpenAI clients send it; we include the model for parity.
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "messages": messages or [{"role": "user", "content": "ping"}],
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


PRICING_USD_PER_1K = _PRICING_USD_PER_1K


__all__ = ["AzureOpenAiProvider", "PRICING_USD_PER_1K"]
