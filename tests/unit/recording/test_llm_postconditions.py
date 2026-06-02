# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the LLM-backed postcondition suggester."""

from __future__ import annotations

from typing import Any

import pytest
from engine.recording import RecordingTrace, llm_postconditions
from engine.recording.trace import RecordingStep


def _trace() -> RecordingTrace:
    return RecordingTrace(
        schema_version="1",
        name="checkout",
        base_url="https://shop.example.com",
        priority="p0",
        steps=(
            RecordingStep(action="navigate", url="https://shop.example.com/"),
            RecordingStep(action="click", selector="#add-to-cart"),
            RecordingStep(action="fill", selector="#email", value="x@example.com"),
        ),
    )


def test_falls_back_when_provider_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine.llm import defaults as llm_defaults

    monkeypatch.setattr(llm_defaults, "get_default_provider", lambda: None)
    out = llm_postconditions(_trace())
    # Falls back to deterministic — at minimum includes the last interactive selector.
    assert any("#email" in line for line in out)


def test_uses_provider_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine.llm import defaults as llm_defaults
    from engine.llm.protocol import LlmResponse

    class _StubProvider:
        name = "stub"

        def complete(self, request: Any) -> LlmResponse:
            return LlmResponse(
                text='{"assertions": ["page.locator(\'#thank-you\')"]}',
                parsed={"assertions": ["page.locator('#thank-you')"]},
                usage={"input_tokens": 100, "output_tokens": 20},
                cost_usd=0.0,
                latency_ms=12,
                provider="stub",
                model="stub-model",
                available=True,
            )

    monkeypatch.setattr(llm_defaults, "get_default_provider", lambda: _StubProvider())
    out = llm_postconditions(_trace())
    assert "page.locator('#thank-you')" in out


def test_falls_back_when_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine.llm import defaults as llm_defaults

    class _Boom:
        def complete(self, request: Any) -> Any:
            raise RuntimeError("provider exploded")

    monkeypatch.setattr(llm_defaults, "get_default_provider", lambda: _Boom())
    out = llm_postconditions(_trace())
    # Did not propagate the exception — and we got at least one suggestion.
    assert out


def test_falls_back_on_unavailable_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine.llm import defaults as llm_defaults
    from engine.llm.protocol import LlmResponse

    class _UnavailableProvider:
        def complete(self, request: Any) -> LlmResponse:
            return LlmResponse(
                text="",
                parsed=None,
                usage={"input_tokens": 0, "output_tokens": 0},
                cost_usd=0.0,
                latency_ms=0,
                provider="off",
                model="off",
                available=False,
            )

    monkeypatch.setattr(llm_defaults, "get_default_provider", lambda: _UnavailableProvider())
    out = llm_postconditions(_trace())
    # Still got a non-empty deterministic fallback.
    assert out


def test_falls_back_when_parsed_assertions_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.llm import defaults as llm_defaults
    from engine.llm.protocol import LlmResponse

    class _EmptyProvider:
        def complete(self, request: Any) -> LlmResponse:
            return LlmResponse(
                text='{"assertions": []}',
                parsed={"assertions": []},
                usage={"input_tokens": 50, "output_tokens": 5},
                cost_usd=0.0,
                latency_ms=10,
                provider="stub",
                model="stub-model",
                available=True,
            )

    monkeypatch.setattr(llm_defaults, "get_default_provider", lambda: _EmptyProvider())
    out = llm_postconditions(_trace())
    assert out  # deterministic fallback kicked in
