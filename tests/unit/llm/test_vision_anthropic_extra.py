# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Extra coverage for the Anthropic vision adapter."""

from __future__ import annotations

import os
from unittest.mock import patch

from engine.llm.vision import _VisionMessage
from engine.llm.vision_anthropic import (
    _extract_first_text,
    anthropic_vision_adapter,
)


def test_adapter_reads_api_key_from_environment() -> None:
    captured: dict[str, object] = {}

    def fake_transport(method, url, headers, json):
        captured["url"] = url
        captured["api_key"] = headers.get("x-api-key")
        return (200, {"content": [{"type": "text", "text": "x"}]})

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}, clear=False):
        response = anthropic_vision_adapter(
            _VisionMessage("s", "u", "aGk=", "image/png"),
            "claude-3-5-sonnet-latest",
            transport=fake_transport,
        )
    assert response.available is True
    assert captured["api_key"] == "env-key"


def test_extract_first_text_skips_non_text_blocks() -> None:
    body = {
        "content": [
            {"type": "image", "source": {}},
            {"type": "text", "text": "real answer"},
        ]
    }
    assert _extract_first_text(body) == "real answer"


def test_extract_first_text_returns_empty_when_no_content() -> None:
    assert _extract_first_text({}) == ""
    assert _extract_first_text({"content": "not-a-list"}) == ""


def test_extract_first_text_handles_missing_text_field() -> None:
    body = {"content": [{"type": "text"}]}
    assert _extract_first_text(body) == ""
