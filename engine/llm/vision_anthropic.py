# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Anthropic vision adapter (v1.4.0).

Builds the Messages-API payload for a screenshot analysis and returns
the model's verbatim text. Kept separate from :mod:`engine.llm.vision`
so importing the bridge doesn't drag in ``httpx`` / Anthropic SDK on
the cold CLI path.
"""

from __future__ import annotations

import os
from typing import Any

from engine.llm.vision import ProviderResponse, _VisionMessage

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
ANTHROPIC_DEFAULT_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION_HEADER = "2023-06-01"
ANTHROPIC_DEFAULT_TIMEOUT_SECONDS = 30.0


def build_anthropic_payload(message: _VisionMessage, model: str) -> dict[str, Any]:
    """Build the JSON body for ``POST /v1/messages`` with an image block."""

    return {
        "model": model,
        "max_tokens": 160,
        "system": message.system,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": message.image_media_type,
                            "data": message.image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": message.user_text,
                    },
                ],
            }
        ],
    }


def anthropic_vision_adapter(
    message: _VisionMessage,
    model: str,
    *,
    transport: object | None = None,
    api_key: str | None = None,
    endpoint: str = ANTHROPIC_DEFAULT_ENDPOINT,
    timeout_seconds: float = ANTHROPIC_DEFAULT_TIMEOUT_SECONDS,
) -> ProviderResponse:
    """POST to ``/v1/messages`` and return the first text block.

    ``transport`` is the test seam — a callable
    ``(method, url, headers, json) -> (status, body)``. When omitted we
    build a real :class:`httpx.Client` lazily.
    """

    key = api_key or os.environ.get(ANTHROPIC_API_KEY_ENV, "").strip()
    if not key:
        return ProviderResponse(
            text="",
            available=False,
            detail=f"{ANTHROPIC_API_KEY_ENV} is not set.",
        )

    payload = build_anthropic_payload(message, model)
    headers = {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION_HEADER,
        "content-type": "application/json",
    }

    if transport is None:
        try:
            import httpx
        except ImportError as exc:
            return ProviderResponse(
                text="",
                available=False,
                detail=f"httpx not available: {exc}",
            )

        def _transport(method: str, url: str, headers: dict, json: dict) -> tuple[int, dict]:
            with httpx.Client(timeout=timeout_seconds) as client:
                resp = client.request(method, url, headers=headers, json=json)
                return resp.status_code, resp.json()

        transport = _transport

    try:
        status, body = transport(  # type: ignore[operator]
            "POST", endpoint, headers, payload
        )
    except Exception as exc:
        return ProviderResponse(
            text="",
            available=False,
            detail=f"transport raised: {type(exc).__name__}: {exc}",
        )

    if status != 200:
        return ProviderResponse(
            text="",
            available=False,
            detail=f"non-200 from Anthropic: {status}",
        )

    text = _extract_first_text(body)
    if not text:
        return ProviderResponse(
            text="",
            available=False,
            detail="response had no text block",
        )
    return ProviderResponse(text=text, available=True)


def _extract_first_text(body: dict[str, Any]) -> str:
    """Return the first ``content[].text`` block from a Messages response."""

    content = body.get("content")
    if not isinstance(content, list):
        return ""
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                return text
    return ""


__all__ = [
    "ANTHROPIC_API_KEY_ENV",
    "ANTHROPIC_DEFAULT_ENDPOINT",
    "ANTHROPIC_DEFAULT_TIMEOUT_SECONDS",
    "ANTHROPIC_VERSION_HEADER",
    "anthropic_vision_adapter",
    "build_anthropic_payload",
]
