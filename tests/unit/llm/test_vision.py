# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the vision LLM bridge."""

from __future__ import annotations

import base64

from engine.llm.vision import (
    MIN_SCREENSHOT_BYTES,
    ProviderResponse,
    VisionRequest,
    _VisionMessage,
    analyze_failure_screenshot,
    build_vision_message,
    sanitise_sentence,
)
from engine.llm.vision_anthropic import (
    anthropic_vision_adapter,
    build_anthropic_payload,
)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff\xe0\x00\x10JFIF"


def test_build_vision_message_contains_locked_system_prompt() -> None:
    request = VisionRequest(
        screenshot_bytes=_PNG_MAGIC + b"\x00" * 4096,
        failure_summary="login button click did not navigate",
        page_url="https://app.example.com/login",
    )
    message = build_vision_message(request)
    assert "ONE concise sentence" in message.system
    assert "login button click" in message.user_text
    assert "https://app.example.com/login" in message.user_text
    assert message.image_media_type == "image/png"


def test_build_vision_message_truncates_long_summaries() -> None:
    request = VisionRequest(
        screenshot_bytes=_PNG_MAGIC + b"\x00" * 4096,
        failure_summary="x" * 5000,
    )
    message = build_vision_message(request)
    assert "xxxxxxxxxx" in message.user_text
    assert len(message.user_text) < 5000


def test_build_vision_message_detects_jpeg() -> None:
    request = VisionRequest(screenshot_bytes=_JPEG_MAGIC + b"\x00" * 4096)
    message = build_vision_message(request)
    assert message.image_media_type == "image/jpeg"


def test_build_vision_message_encodes_base64() -> None:
    body = _PNG_MAGIC + b"hello"
    request = VisionRequest(screenshot_bytes=body)
    message = build_vision_message(request)
    decoded = base64.b64decode(message.image_base64)
    assert decoded == body


def test_sanitise_sentence_collapses_whitespace() -> None:
    assert sanitise_sentence("  Hello   world  \n  again  ") == "Hello world again."


def test_sanitise_sentence_caps_length_with_ellipsis() -> None:
    long = "a" * 1000
    out = sanitise_sentence(long)
    assert len(out) <= 280
    assert out.endswith("…")


def test_sanitise_sentence_keeps_terminal_punctuation() -> None:
    assert sanitise_sentence("Is the user logged in?") == "Is the user logged in?"


def test_sanitise_sentence_empty_returns_empty() -> None:
    assert sanitise_sentence("   ") == ""


def test_analyze_with_synthetic_adapter() -> None:
    request = VisionRequest(
        screenshot_bytes=_PNG_MAGIC + b"\x00" * 4096,
        failure_summary="click failed",
    )

    def stub(_message: _VisionMessage, _model: str) -> ProviderResponse:
        return ProviderResponse(
            text="The user sees the login page with an error toast.",
            available=True,
        )

    analysis = analyze_failure_screenshot(request, adapter=stub)
    assert analysis.available is True
    assert "login page" in analysis.sentence
    assert analysis.screenshot_hash


def test_analyze_returns_unavailable_when_adapter_raises() -> None:
    request = VisionRequest(screenshot_bytes=_PNG_MAGIC + b"\x00" * 4096)

    def boom(*_args, **_kwargs) -> ProviderResponse:
        raise RuntimeError("network down")

    analysis = analyze_failure_screenshot(request, adapter=boom)
    assert analysis.available is False
    assert "network down" in analysis.detail


def test_analyze_returns_unavailable_when_no_adapter_for_provider() -> None:
    request = VisionRequest(screenshot_bytes=_PNG_MAGIC + b"\x00" * 4096)
    analysis = analyze_failure_screenshot(request, provider_name="openai")
    assert analysis.available is False
    assert "openai" in analysis.detail


def test_min_screenshot_bytes_is_a_reasonable_floor() -> None:
    """A favicon-sized PNG falls below the floor; a real screenshot is above."""

    assert MIN_SCREENSHOT_BYTES > 1024
    assert MIN_SCREENSHOT_BYTES < 64 * 1024


# --------------------------------------------------------------------------- #
# Anthropic adapter
# --------------------------------------------------------------------------- #


def test_anthropic_payload_includes_image_block() -> None:
    message = _VisionMessage(
        system="sys",
        user_text="user",
        image_base64="aGVsbG8=",
        image_media_type="image/png",
    )
    payload = build_anthropic_payload(message, model="claude-3-5-sonnet-latest")
    assert payload["model"] == "claude-3-5-sonnet-latest"
    assert payload["system"] == "sys"
    blocks = payload["messages"][0]["content"]
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["media_type"] == "image/png"
    assert blocks[1]["type"] == "text"
    assert blocks[1]["text"] == "user"


def test_anthropic_adapter_requires_api_key() -> None:
    response = anthropic_vision_adapter(
        _VisionMessage("s", "u", "aGk=", "image/png"),
        "claude-3-5-sonnet-latest",
        transport=lambda *a, **k: (200, {}),
        api_key=None,
    )
    assert response.available is False
    assert "ANTHROPIC_API_KEY" in response.detail


def test_anthropic_adapter_returns_first_text_block() -> None:
    captured: dict[str, object] = {}

    def fake_transport(method, url, headers, json):
        captured["method"] = method
        captured["url"] = url
        captured["api_key_header"] = headers.get("x-api-key")
        return (
            200,
            {
                "content": [
                    {"type": "text", "text": "The user sees a dashboard."},
                ]
            },
        )

    response = anthropic_vision_adapter(
        _VisionMessage("s", "u", "aGk=", "image/png"),
        "claude-3-5-sonnet-latest",
        transport=fake_transport,
        api_key="sk-test",
    )
    assert response.available is True
    assert response.text == "The user sees a dashboard."
    assert captured["api_key_header"] == "sk-test"


def test_anthropic_adapter_handles_non_200() -> None:
    def fake_transport(*_a, **_k):
        return (429, {"error": "rate limited"})

    response = anthropic_vision_adapter(
        _VisionMessage("s", "u", "aGk=", "image/png"),
        "claude-3-5-sonnet-latest",
        transport=fake_transport,
        api_key="sk-test",
    )
    assert response.available is False
    assert "429" in response.detail


def test_anthropic_adapter_handles_missing_text_block() -> None:
    def fake_transport(*_a, **_k):
        return (200, {"content": [{"type": "image", "source": {}}]})

    response = anthropic_vision_adapter(
        _VisionMessage("s", "u", "aGk=", "image/png"),
        "claude-3-5-sonnet-latest",
        transport=fake_transport,
        api_key="sk-test",
    )
    assert response.available is False
    assert "no text block" in response.detail


def test_anthropic_adapter_handles_transport_exception() -> None:
    def boom(*_a, **_k):
        raise OSError("connection refused")

    response = anthropic_vision_adapter(
        _VisionMessage("s", "u", "aGk=", "image/png"),
        "claude-3-5-sonnet-latest",
        transport=boom,
        api_key="sk-test",
    )
    assert response.available is False
    assert "connection refused" in response.detail
