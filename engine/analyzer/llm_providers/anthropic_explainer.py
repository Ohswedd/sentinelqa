"""Anthropic explainer adapter (ADR-0014).

Posts directly to the Messages API. Anthropic doesn't have an explicit
JSON-mode toggle; the locked prompt enforces JSON-only output and the
analyzer validates strictly on the way back in.
"""

from __future__ import annotations

import json
from typing import Any

from engine.analyzer.llm_explainer import HttpLlmExplainerBase


class AnthropicLlmExplainer(HttpLlmExplainerBase):
    name = "anthropic"

    DEFAULT_MODEL: str = "claude-haiku-4-5-20251001"
    ENDPOINT: str = "https://api.anthropic.com/v1/messages"
    API_VERSION: str = "2023-06-01"

    def endpoint_url(self) -> str:
        return self.ENDPOINT

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": self.API_VERSION,
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
            "max_tokens": 512,
            "system": prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
        }

    def extract_response_text(self, body: dict[str, Any]) -> str:
        content = body.get("content") or []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    return text
        return "{}"

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        usage = body.get("usage") or {}
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))


__all__ = ["AnthropicLlmExplainer"]
