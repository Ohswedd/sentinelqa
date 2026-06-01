# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Extra coverage for the vision bridge core."""

from __future__ import annotations

from engine.llm import vision
from engine.llm.vision import VisionRequest, analyze_failure_screenshot


def test_resolve_adapter_returns_null_for_null_provider() -> None:
    assert vision._resolve_adapter("null") is not None


def test_resolve_adapter_returns_none_for_unwired_providers() -> None:
    assert vision._resolve_adapter("anthropic") is None
    assert vision._resolve_adapter("openai") is None
    assert vision._resolve_adapter("gemini") is None


def test_null_adapter_returns_unavailable() -> None:
    response = vision._null_adapter(
        vision._VisionMessage("s", "u", "aGk=", "image/png"),
        "claude-3-5-sonnet-latest",
    )
    assert response.available is False
    assert "Null" in response.detail


def test_analyze_resolves_unwired_provider_to_no_adapter() -> None:
    """When no adapter is supplied for ``anthropic`` we get a clean degrade."""

    request = VisionRequest(
        screenshot_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 4096,
        failure_summary="test",
    )
    analysis = analyze_failure_screenshot(request, provider_name="anthropic")
    assert analysis.available is False
    assert "anthropic" in analysis.detail


def test_infer_media_type_handles_gif() -> None:
    msg = vision.build_vision_message(VisionRequest(screenshot_bytes=b"GIF89a" + b"\x00" * 4096))
    assert msg.image_media_type == "image/gif"


def test_infer_media_type_handles_webp() -> None:
    msg = vision.build_vision_message(
        VisionRequest(screenshot_bytes=b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 4000)
    )
    assert msg.image_media_type == "image/webp"
