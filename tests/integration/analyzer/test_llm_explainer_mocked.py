"""Mocked-LLM end-to-end test."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from engine.analyzer.categorize import categorize
from engine.analyzer.llm_explainer import (
    HttpLlmExplainerBase,
    NullLlmExplainer,
    ProviderConfigError,
    build_llm_explainer,
)
from engine.analyzer.llm_providers.anthropic_explainer import AnthropicLlmExplainer
from engine.analyzer.llm_providers.openai_explainer import OpenAiLlmExplainer
from engine.analyzer.pipeline import Analyzer
from engine.analyzer.root_cause import hypothesize
from engine.config.schema import AnalyzerLlmConfig

from tests.unit.analyzer.conftest import make_signal


def _stub_http_client(response_body: dict[str, Any], status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=response_body)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_openai_explainer_refines_through_mocked_http(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    )
    client = _stub_http_client(
        {
            "choices": [
                {"message": {"content": json.dumps({"refinement": "fits the evidence."})}},
            ],
            "usage": {"prompt_tokens": 200, "completion_tokens": 30},
        }
    )
    explainer = OpenAiLlmExplainer(config=cfg, http_client=client)
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    refinement = explainer.refine(signal, cls, hyp)
    assert refinement == "fits the evidence."
    assert explainer.usage.requests == 1
    assert explainer.usage.cost_usd > 0


def test_anthropic_explainer_refines_through_mocked_http(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        api_key_env="ANTHROPIC_API_KEY",
    )
    client = _stub_http_client(
        {
            "content": [
                {"type": "text", "text": json.dumps({"refinement": "DB pool exhausted."})},
            ],
            "usage": {"input_tokens": 250, "output_tokens": 40},
        }
    )
    explainer = AnthropicLlmExplainer(config=cfg, http_client=client)
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    refinement = explainer.refine(signal, cls, hyp)
    assert refinement == "DB pool exhausted."


def test_explainer_returns_none_on_malformed_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    )
    # Provider returns non-JSON in `content` — explainer must swallow it.
    client = _stub_http_client(
        {
            "choices": [{"message": {"content": "not json at all"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
    )
    explainer = OpenAiLlmExplainer(config=cfg, http_client=client)
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    assert explainer.refine(signal, cls, hyp) is None
    # Usage is still tracked.
    assert explainer.usage.requests == 1


def test_explainer_returns_none_when_choices_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    )
    client = _stub_http_client({"choices": []})
    explainer = OpenAiLlmExplainer(config=cfg, http_client=client)
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    assert explainer.refine(signal, cls, hyp) is None


def test_explainer_returns_none_when_anthropic_text_block_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
    )
    client = _stub_http_client({"content": [{"type": "image", "data": "..."}]})
    explainer = AnthropicLlmExplainer(config=cfg, http_client=client)
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    assert explainer.refine(signal, cls, hyp) is None


def test_explainer_raises_without_api_key_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        api_key_env="OPENAI_API_KEY",
    )
    explainer = OpenAiLlmExplainer(config=cfg, http_client=_stub_http_client({}))
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    with pytest.raises(ProviderConfigError):
        explainer.refine(signal, cls, hyp)


def test_explainer_raises_when_api_key_env_unset_in_config(monkeypatch):
    cfg = AnalyzerLlmConfig(enabled=True, provider="openai", api_key_env=None)
    explainer = OpenAiLlmExplainer(config=cfg, http_client=_stub_http_client({}))
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    with pytest.raises(ProviderConfigError):
        explainer.refine(signal, cls, hyp)


def test_pipeline_integrates_mocked_explainer(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        api_key_env="OPENAI_API_KEY",
    )
    client = _stub_http_client(
        {
            "choices": [
                {"message": {"content": json.dumps({"refinement": "added context"})}},
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
    )
    explainer = OpenAiLlmExplainer(config=cfg, http_client=client)
    analyzer = Analyzer(llm=explainer)
    signal = make_signal()
    result = analyzer.analyze_one(signal)
    assert result.hypothesis.llm_refinement == "added context"
    # Deterministic core is preserved.
    assert result.classification.category == "unknown"  # signal has no rules matching


def test_build_llm_explainer_factory_disabled():
    assert isinstance(build_llm_explainer(AnalyzerLlmConfig(enabled=False)), NullLlmExplainer)


def test_explainer_skips_request_when_budget_exhausted(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        api_key_env="OPENAI_API_KEY",
        max_usd_per_run=0.0001,
    )

    # Pre-populate usage so the budget is already exceeded on next call.
    explainer = OpenAiLlmExplainer(config=cfg, http_client=_stub_http_client({}))
    explainer._state._usage = explainer._state._usage.add(
        input_tokens=10_000,
        output_tokens=10_000,
        cost_usd=10.0,
    )
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    assert explainer.refine(signal, cls, hyp) is None


def test_explainer_skips_request_when_projected_cost_exceeds_budget(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    # Budget too small to fit even a tiny prompt: ensure pre-flight catches it.
    cfg = AnalyzerLlmConfig(
        enabled=True,
        provider="openai",
        api_key_env="OPENAI_API_KEY",
        max_usd_per_run=0.000001,
    )
    explainer = OpenAiLlmExplainer(config=cfg, http_client=_stub_http_client({}))
    signal = make_signal()
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    assert explainer.refine(signal, cls, hyp) is None


def test_http_base_class_is_abstract():
    # The base class itself shouldn't be instantiable for refining — but the
    # constructor doesn't enforce that; instead the overridable hooks raise.
    # This test documents that contract.
    cfg = AnalyzerLlmConfig(enabled=True, provider="openai", api_key_env="X")
    base = HttpLlmExplainerBase(config=cfg, http_client=_stub_http_client({}))
    with pytest.raises(NotImplementedError):
        base.endpoint_url()
    with pytest.raises(NotImplementedError):
        base.auth_headers(api_key="x")
    with pytest.raises(NotImplementedError):
        base.build_payload(prompt="", summary={}, model="")
    with pytest.raises(NotImplementedError):
        base.extract_response_text({})
