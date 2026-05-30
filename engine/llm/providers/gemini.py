"""Google Gemini provider (Phase 30 task 30.02, ADR-0042).

Calls Google AI Studio's REST endpoint:
``https://generativelanguage.googleapis.com/v1/models/<model>:generateContent``.
No ``google-generativeai`` SDK is imported.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from engine.errors.base import LlmMissingKeyError
from engine.llm.budget import estimate_cost_usd
from engine.llm.protocol import LlmRequest, ProviderHealth
from engine.llm.providers._http_base import HttpLlmProviderBase

# Per-1k-token USD rates. October-2024 list-price snapshot. Gemini's
# pricing distinguishes between input ≤ 128k and > 128k tokens; the
# defaults here are the ≤ 128k tier (most common in SentinelQA's
# bounded summaries).
_PRICING_USD_PER_1K: dict[str, tuple[float, float]] = {
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-2.0-flash": (0.0001, 0.0004),
}


@dataclass
class GeminiProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "gemini"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "gemini-1.5-flash"
    API_KEY_ENV: ClassVar[str] = "GEMINI_API_KEY"
    BASE_URL: ClassVar[str] = "https://generativelanguage.googleapis.com/v1/models"

    def endpoint_url(self) -> str:
        model = self.model or self.DEFAULT_MODEL
        return f"{self.BASE_URL}/{model}:generateContent"

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        # Gemini accepts the API key either as ``?key=`` query arg or as
        # the ``x-goog-api-key`` header. The header keeps secrets out of
        # URLs (and out of `httpx`'s URL representation), which matters
        # for the redacted audit log.
        return {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

    def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        for msg in request.messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}],
                }
            )
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "ping"}]}]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
        }
        if request.system:
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        if request.response_schema is not None:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = request.response_schema
        return payload

    def extract_response_text(self, body: dict[str, Any]) -> str:
        candidates = body.get("candidates") or []
        for cand in candidates:
            content = cand.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                text = part.get("text")
                if isinstance(text, str):
                    return text
        return "{}"

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        usage = body.get("usageMetadata") or {}
        return int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0))

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

    def doctor(self) -> ProviderHealth:
        """1-token ping with explicit Gemini error handling."""

        try:
            api_key = self._resolve_api_key()
        except LlmMissingKeyError:
            return ProviderHealth(
                provider=self.name,
                model=self.model or self.DEFAULT_MODEL,
                status="unavailable",
                latency_ms=0.0,
                detail=f"env var {self.API_KEY_ENV!r} is not set",
            )

        probe = LlmRequest(
            system="",
            messages=({"role": "user", "content": "ping"},),
            max_output_tokens=1,
            caller="doctor",
        )
        model = self.model or self.DEFAULT_MODEL
        payload = self.build_payload(request=probe, model=model)
        client = self.http_client or httpx.Client(timeout=self.request_timeout_seconds)
        owns = self.http_client is None
        start = time.perf_counter()
        try:
            try:
                response = client.post(
                    self.endpoint_url(),
                    json=payload,
                    headers=self.auth_headers(api_key=api_key),
                )
            except httpx.HTTPError as exc:
                return ProviderHealth(
                    provider=self.name,
                    model=model,
                    status="unavailable",
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    detail=f"transport error: {type(exc).__name__}",
                )
        finally:
            if owns:
                client.close()
        latency_ms = (time.perf_counter() - start) * 1000.0
        if 200 <= response.status_code < 300:
            return ProviderHealth(
                provider=self.name,
                model=model,
                status="available",
                latency_ms=latency_ms,
                detail="ok",
            )
        if response.status_code in {401, 403}:
            return ProviderHealth(
                provider=self.name,
                model=model,
                status="unavailable",
                latency_ms=latency_ms,
                detail=f"auth rejected: HTTP {response.status_code}",
            )
        return ProviderHealth(
            provider=self.name,
            model=model,
            status="degraded",
            latency_ms=latency_ms,
            detail=f"HTTP {response.status_code}",
        )


PRICING_USD_PER_1K = _PRICING_USD_PER_1K


__all__ = ["GeminiProvider", "PRICING_USD_PER_1K"]
