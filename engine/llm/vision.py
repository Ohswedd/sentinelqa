# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Vision LLM bridge — "what does the user see?" analysis (v1.4.0).

The deterministic side of the audit knows *what failed* — assertion
text, network responses, console errors. It doesn't know *what the
user sees when the page is on screen*. When a Playwright screenshot
exists, a vision-capable LLM can summarise the visible state in a
single sentence and that sentence sits next to the screenshot in
the HTML report.

This module is intentionally provider-agnostic: it builds a
:class:`VisionRequest` from a screenshot + failure context and hands
it to a provider-specific adapter. Today we ship the Anthropic
adapter (the only one we use in CI); OpenAI / Gemini stubs return
``available=False`` so callers degrade gracefully.

The output is :class:`VisionAnalysis` — a single, pre-redacted
sentence the reporter renders verbatim. The prompt is locked
(no caller input is forwarded into the system prompt) so the
output stays bounded.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

VisionProviderName = Literal["anthropic", "openai", "gemini", "null"]


@dataclass(frozen=True, slots=True)
class VisionRequest:
    """A single vision call."""

    screenshot_bytes: bytes
    failure_summary: str = ""
    page_url: str = ""
    max_output_tokens: int = 120
    model: str = "claude-3-5-sonnet-latest"


@dataclass(frozen=True, slots=True)
class VisionAnalysis:
    """The result of one vision call, ready for the reporter."""

    sentence: str
    provider: str
    model: str
    available: bool
    detail: str = ""
    screenshot_hash: str = ""


# The locked system prompt. Keeping every word here means we can
# golden-test the bytes the provider sees. The "ONE sentence"
# instruction prevents the model from emitting a paragraph that
# breaks the HTML report's layout.
_SYSTEM_PROMPT: Final[str] = (
    "You are an expert QA engineer reviewing a screenshot from an "
    "automated test failure. Describe in ONE concise sentence what "
    "the user would see on screen. Do not speculate about the cause "
    "of the failure. Do not produce more than 280 characters. "
    "If the screenshot is blank, say so explicitly."
)


# The locked user-message template. The {failure_summary} block is
# truncated before substitution so a runaway message can't blow the
# token budget.
_USER_TEMPLATE: Final[str] = (
    "Test failure summary (deterministic side):\n"
    "{failure_summary}\n\n"
    "Page URL: {page_url}\n\n"
    "Look at the attached screenshot and describe what the user "
    "currently sees, in one sentence."
)


# Maximum number of characters from the failure summary that flow
# into the prompt. The deterministic side already produces concise
# titles; truncating here keeps the request bounded.
_FAILURE_SUMMARY_CAP: Final[int] = 1024
_SCREENSHOT_BYTES_CAP: Final[int] = 5 * 1024 * 1024  # 5 MiB

# Re-used by the reporter to decide whether a screenshot is "rich
# enough" to send through vision. Tiny placeholder screenshots
# (favicon-sized) are skipped to keep cost down.
MIN_SCREENSHOT_BYTES: Final[int] = 4 * 1024


@dataclass(frozen=True, slots=True)
class _VisionMessage:
    """Provider-agnostic shape: text + base64 image."""

    system: str
    user_text: str
    image_base64: str
    image_media_type: str


def build_vision_message(request: VisionRequest) -> _VisionMessage:
    """Compose the locked-prompt vision message bytes."""

    summary = request.failure_summary.strip()[:_FAILURE_SUMMARY_CAP] or "(no summary)"
    user_text = _USER_TEMPLATE.format(
        failure_summary=summary,
        page_url=request.page_url or "(unknown)",
    )
    body = request.screenshot_bytes[:_SCREENSHOT_BYTES_CAP]
    image_b64 = base64.b64encode(body).decode("ascii")
    media_type = _infer_image_media_type(body)
    return _VisionMessage(
        system=_SYSTEM_PROMPT,
        user_text=user_text,
        image_base64=image_b64,
        image_media_type=media_type,
    )


# --------------------------------------------------------------------------- #
# Sentence sanitisation
# --------------------------------------------------------------------------- #

_WHITESPACE_RE = re.compile(r"\s+")
_MAX_SENTENCE_CHARS: Final[int] = 280


def sanitise_sentence(raw: str) -> str:
    """Collapse whitespace + cap length to a single render-safe sentence."""

    collapsed = _WHITESPACE_RE.sub(" ", raw).strip()
    if not collapsed:
        return ""
    if len(collapsed) > _MAX_SENTENCE_CHARS:
        collapsed = collapsed[: _MAX_SENTENCE_CHARS - 1].rstrip() + "…"
    if not collapsed.endswith((".", "!", "?", "…")):
        collapsed += "."
    return collapsed


# --------------------------------------------------------------------------- #
# Provider adapter dispatch
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """The provider's verbatim text + availability flag."""

    text: str
    available: bool
    detail: str = ""


def analyze_failure_screenshot(
    request: VisionRequest,
    *,
    provider_name: VisionProviderName = "anthropic",
    adapter: object | None = None,
) -> VisionAnalysis:
    """Run the screenshot through the configured vision provider.

    ``adapter`` is the test seam — when omitted we look up the
    canonical adapter for ``provider_name``. The adapter must be a
    callable ``(message: _VisionMessage, model: str) ->
    ProviderResponse``.
    """

    message = build_vision_message(request)
    screenshot_hash = hashlib.sha256(request.screenshot_bytes).hexdigest()[:16]

    if adapter is None:
        adapter = _resolve_adapter(provider_name)

    if adapter is None:
        return VisionAnalysis(
            sentence="",
            provider=provider_name,
            model=request.model,
            available=False,
            detail=f"No vision adapter registered for provider {provider_name!r}.",
            screenshot_hash=screenshot_hash,
        )

    try:
        response = adapter(message, request.model)  # type: ignore[operator]
    except Exception as exc:
        return VisionAnalysis(
            sentence="",
            provider=provider_name,
            model=request.model,
            available=False,
            detail=f"adapter raised: {type(exc).__name__}: {exc}",
            screenshot_hash=screenshot_hash,
        )

    sentence = sanitise_sentence(response.text)
    return VisionAnalysis(
        sentence=sentence,
        provider=provider_name,
        model=request.model,
        available=response.available and bool(sentence),
        detail=response.detail,
        screenshot_hash=screenshot_hash,
    )


def _resolve_adapter(provider_name: VisionProviderName):
    """Return the canonical adapter callable for a provider, or ``None``."""

    if provider_name == "null":
        return _null_adapter
    # Real adapter wiring lives outside this module so importing
    # ``engine.llm.vision`` from a cold CLI doesn't drag in httpx /
    # provider SDKs. Callers wire their adapter explicitly.
    return None


def _null_adapter(message: _VisionMessage, model: str) -> ProviderResponse:
    """Always-unavailable adapter used by tests + the null provider."""

    _ = message, model
    return ProviderResponse(
        text="",
        available=False,
        detail="Null vision adapter; no remote endpoint.",
    )


# --------------------------------------------------------------------------- #
# Image type sniffing — PNG / JPEG / WebP magic bytes
# --------------------------------------------------------------------------- #


def _infer_image_media_type(body: bytes) -> str:
    """Sniff the image MIME type from the first few bytes."""

    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if body[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    if body[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    # Default to PNG — Playwright defaults to it, and the provider
    # will reject anything truly unrecognisable.
    return "image/png"


def load_screenshot(path: Path) -> bytes:
    """Read the screenshot bytes from disk. Caller catches the OSError."""

    return path.read_bytes()


__all__ = [
    "MIN_SCREENSHOT_BYTES",
    "ProviderResponse",
    "VisionAnalysis",
    "VisionProviderName",
    "VisionRequest",
    "analyze_failure_screenshot",
    "build_vision_message",
    "load_screenshot",
    "sanitise_sentence",
]
