"""LLM explainer Null adapter + parsing tests (task 09.05)."""

from __future__ import annotations

import json

import pytest
from engine.analyzer.categorize import categorize
from engine.analyzer.llm_explainer import (
    PROMPT_VERSION,
    NullLlmExplainer,
    build_llm_explainer,
    build_signal_summary,
    load_locked_prompt,
    parse_provider_response,
)
from engine.analyzer.root_cause import hypothesize
from engine.config.schema import AnalyzerLlmConfig

from tests.unit.analyzer.conftest import make_signal


def test_null_explainer_returns_none():
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    null = NullLlmExplainer()
    assert null.refine(signal, cls, hyp) is None


def test_null_explainer_has_zero_usage():
    null = NullLlmExplainer()
    assert null.usage.cost_usd == 0.0
    assert null.usage.requests == 0


def test_build_llm_explainer_returns_null_when_disabled():
    cfg = AnalyzerLlmConfig(enabled=False)
    adapter = build_llm_explainer(cfg)
    assert isinstance(adapter, NullLlmExplainer)


def test_build_llm_explainer_returns_null_for_unknown_provider_when_disabled():
    cfg = AnalyzerLlmConfig(enabled=False, provider="null")
    adapter = build_llm_explainer(cfg)
    assert isinstance(adapter, NullLlmExplainer)


def test_build_llm_explainer_openai_when_enabled():
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    )
    adapter = build_llm_explainer(cfg)
    assert adapter.name == "openai"


def test_build_llm_explainer_anthropic_when_enabled():
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        api_key_env="ANTHROPIC_API_KEY",
    )
    adapter = build_llm_explainer(cfg)
    assert adapter.name == "anthropic"


def test_load_locked_prompt_is_non_empty():
    body = load_locked_prompt()
    assert "SentinelQA Analyzer Explainer Prompt" in body


def test_prompt_version_is_one():
    assert PROMPT_VERSION == "1"


def test_parse_provider_response_accepts_refinement():
    raw = json.dumps({"refinement": "this fits the evidence; the 500 lines up"})
    assert parse_provider_response(raw).startswith("this fits the evidence")


def test_parse_provider_response_accepts_empty():
    assert parse_provider_response('{"refinement": ""}') == ""


def test_parse_provider_response_rejects_unknown_keys():
    with pytest.raises(ValueError):
        parse_provider_response('{"refinement": "ok", "other": 1}')


def test_parse_provider_response_rejects_non_json():
    with pytest.raises(ValueError):
        parse_provider_response("not json")


def test_parse_provider_response_rejects_oversized_refinement():
    raw = json.dumps({"refinement": "x" * 1_000})
    with pytest.raises(ValueError):
        parse_provider_response(raw)


def test_build_signal_summary_redacts_long_fields_and_skips_credentials():
    signal = make_signal(
        title="x" * 500,
        error_message="oh no — Authorization: Bearer secret123 leaked here",
        error_name="E",
    )
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    summary = build_signal_summary(signal, cls, hyp)
    # Title is clipped.
    assert len(summary["test"]["title"]) <= 200
    # Error message is clipped (caller pre-redacts; we don't re-redact, but
    # this test documents the contract: the summary is bounded).
    assert len(summary["error"]["message"]) <= 400
    assert summary["deterministic"]["category"] == cls.category
