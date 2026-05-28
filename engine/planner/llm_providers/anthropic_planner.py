"""Anthropic planner adapter (ADR-0011).

Posts directly to the Messages API. Anthropic doesn't have an explicit
JSON-mode toggle; we lean on the locked prompt to enforce JSON-only
output and validate strictly on the way back in.
"""

from __future__ import annotations

from typing import Any

from engine.planner.llm_providers._base import HttpLlmProviderBase


class AnthropicLlmPlanner(HttpLlmProviderBase):
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
        graph_summary: dict[str, Any],
        max_proposals: int,
        model: str,
    ) -> dict[str, Any]:
        import json

        user_message = json.dumps(
            {
                "task": "propose additional flows",
                "schema_version": 1,
                "max_proposals": max_proposals,
                "graph_summary": graph_summary,
            }
        )
        return {
            "model": model or self.DEFAULT_MODEL,
            "max_tokens": 2048,
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


__all__ = ["AnthropicLlmPlanner"]
