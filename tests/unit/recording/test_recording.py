# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the recording → spec pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.recording import (
    RecordingStep,
    RecordingTrace,
    default_postconditions,
    emit_spec,
    parse_trace,
)


def _sample_trace() -> dict[str, object]:
    return {
        "schema_version": "1",
        "name": "checkout-happy-path",
        "base_url": "https://shop.example.com",
        "priority": "p0",
        "steps": [
            {"action": "navigate", "url": "https://shop.example.com/"},
            {"action": "click", "selector": "#add-to-cart"},
            {
                "action": "fill",
                "selector": "#email",
                "value": "user@example.com",
            },
            {"action": "press", "selector": "#email", "key": "Enter"},
            {
                "action": "expect",
                "selector": "#thank-you",
                "assertion": "visible",
            },
        ],
    }


def test_parse_trace_round_trip() -> None:
    trace = parse_trace(_sample_trace())
    assert trace.name == "checkout-happy-path"
    assert trace.priority == "p0"
    assert len(trace.steps) == 5
    assert trace.steps[0].action == "navigate"
    assert trace.steps[2].value == "user@example.com"


def test_parse_trace_from_path(tmp_path: Path) -> None:
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(_sample_trace()), encoding="utf-8")
    trace = parse_trace(path)
    assert trace.name == "checkout-happy-path"


def test_parse_trace_rejects_missing_name() -> None:
    bad = _sample_trace()
    del bad["name"]
    with pytest.raises(ValueError):
        parse_trace(bad)


def test_parse_trace_rejects_unknown_action() -> None:
    bad = _sample_trace()
    bad["steps"] = [{"action": "telepathy", "selector": "#x"}]
    with pytest.raises(ValueError):
        parse_trace(bad)


def test_parse_trace_rejects_bad_priority() -> None:
    bad = _sample_trace()
    bad["priority"] = "p9"
    with pytest.raises(ValueError):
        parse_trace(bad)


def test_emit_spec_contains_tag(tmp_path: Path) -> None:
    trace = parse_trace(_sample_trace())
    spec_path = emit_spec(trace, output_dir=tmp_path, source_label="local-test")
    body = spec_path.read_text(encoding="utf-8")
    assert "test('checkout-happy-path @p0'" in body
    assert "page.goto('https://shop.example.com/')" in body
    assert "page.locator('#add-to-cart').click()" in body
    assert "page.locator('#email').fill('user@example.com')" in body
    assert "expect(page.locator('#thank-you')).toBeVisible()" in body


def test_emit_spec_filename_kebabcases_name(tmp_path: Path) -> None:
    trace = parse_trace(_sample_trace())
    spec_path = emit_spec(trace, output_dir=tmp_path)
    assert spec_path.name == "checkout-happy-path.spec.ts"


def test_emit_spec_writes_generator_banner(tmp_path: Path) -> None:
    trace = parse_trace(_sample_trace())
    spec_path = emit_spec(trace, output_dir=tmp_path, source_label="abc.json")
    body = spec_path.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in body
    assert "abc.json" in body


def test_emit_spec_escapes_single_quotes_in_values(tmp_path: Path) -> None:
    trace = RecordingTrace(
        schema_version="1",
        name="quote-test",
        base_url="https://x.example",
        priority="p3",
        steps=(RecordingStep(action="fill", selector="#name", value="O'Hara"),),
    )
    spec_path = emit_spec(trace, output_dir=tmp_path)
    body = spec_path.read_text(encoding="utf-8")
    assert "O\\'Hara" in body


def test_default_postconditions_returns_last_interactive_selectors() -> None:
    trace = parse_trace(_sample_trace())
    suggestions = default_postconditions(trace)
    assert len(suggestions) == 2
    # The last interactive selectors are #email (from press / fill) and
    # #add-to-cart (from click).
    joined = " ".join(suggestions)
    assert "#email" in joined
    assert "#add-to-cart" in joined


def test_emit_spec_writes_postconditions(tmp_path: Path) -> None:
    trace = parse_trace(_sample_trace())
    spec_path = emit_spec(
        trace,
        output_dir=tmp_path,
        postconditions=("page.locator('#confirmation')",),
    )
    body = spec_path.read_text(encoding="utf-8")
    assert "expect(page.locator('#confirmation')).toBeVisible()" in body
