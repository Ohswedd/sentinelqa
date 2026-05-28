"""OpenAI explainer adapter (ADR-0014).

Uses the Chat Completions endpoint with ``response_format=json_object``
so the provider's output is constrained to valid JSON. No vendor SDK is
imported — we POST directly via ``httpx`` (see
:mod:`engine.planner.llm_providers.openai_planner` for the rationale).
"""

from __future__ import annotations

import json
from typing import Any

from engine.analyzer.llm_explainer import HttpLlmExplainerBase


class OpenAiLlmExplainer(HttpLlmExplainerBase):
    name = "openai"

    DEFAULT_MODEL: str = "gpt-4o-mini"
    ENDPOINT: str = "https://api.openai.com/v1/chat/completions"

    def endpoint_url(self) -> str:
        return self.ENDPOINT

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(
        self,
        *,
        prompt: str,
        summary: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:
        user_message = json.dumps(
            {
                "task": "refine the deterministic failure hypothesis",
                "schema_version": 1,
                "signal_summary": summary,
            }
        )
        return {
            "model": model or self.DEFAULT_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
        }

    def extract_response_text(self, body: dict[str, Any]) -> str:
        choices = body.get("choices") or []
        if not choices:
            return "{}"
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            return "{}"
        return content

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        usage = body.get("usage") or {}
        return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


__all__ = ["OpenAiLlmExplainer"]
