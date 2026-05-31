"""Strict validation for the `llm:` config block (Phase 30, ADR-0042)."""

from __future__ import annotations

import pytest
from engine.config.schema import (
    LlmBudgetConfig,
    LlmConfig,
    LlmProviderConfig,
    LlmRateLimitConfig,
    RootConfig,
)
from pydantic import ValidationError


def test_llm_config_defaults_are_null_provider() -> None:
    cfg = LlmConfig()
    assert cfg.default_provider == "null"
    assert cfg.providers == {}
    assert cfg.budget.max_usd_per_run == 0.50
    assert cfg.rate_limit.requests_per_minute == 60.0


def test_llm_config_accepts_every_known_provider() -> None:
    for name in [
        "anthropic",
        "openai",
        "gemini",
        "ollama",
        "azure_openai",
        "vertex",
        "mistral",
        "groq",
        "openrouter",
    ]:
        cfg = LlmConfig(default_provider=name)  # type: ignore[arg-type]
        assert cfg.default_provider == name


def test_llm_config_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        LlmConfig(default_provider="not-a-real-provider")  # type: ignore[arg-type]


def test_llm_provider_config_accepts_known_keys() -> None:
    p = LlmProviderConfig(
        api_key_env="ANTHROPIC_API_KEY",
        models={"planner": "claude-3-5-sonnet"},
    )
    assert p.api_key_env == "ANTHROPIC_API_KEY"
    assert p.models["planner"] == "claude-3-5-sonnet"


def test_llm_provider_config_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        LlmProviderConfig(unknown_key="nope")  # type: ignore[call-arg]


def test_llm_provider_config_accepts_azure_block() -> None:
    p = LlmProviderConfig(
        api_key_env="AZURE_OPENAI_API_KEY",
        azure_resource="my-resource",
        azure_deployment="gpt4o-prod",
        azure_api_version="2024-08-01-preview",
    )
    assert p.azure_resource == "my-resource"


def test_llm_provider_config_accepts_ollama_host() -> None:
    p = LlmProviderConfig(host="http://localhost:11434")
    assert p.host == "http://localhost:11434"


def test_llm_provider_config_accepts_vertex_block() -> None:
    p = LlmProviderConfig(
        api_key_env="GOOGLE_APPLICATION_CREDENTIALS",
        vertex_project="my-project",
        vertex_region="us-east1",
    )
    assert p.vertex_project == "my-project"
    assert p.vertex_region == "us-east1"


def test_llm_budget_config_validates_range() -> None:
    LlmBudgetConfig(max_usd_per_run=10.0)
    with pytest.raises(ValidationError):
        LlmBudgetConfig(max_usd_per_run=-1.0)
    with pytest.raises(ValidationError):
        LlmBudgetConfig(max_usd_per_run=200.0)


def test_llm_budget_config_per_caller_sub_caps() -> None:
    cfg = LlmBudgetConfig(
        max_usd_per_run=1.0,
        max_usd_planner=0.5,
        max_usd_analyzer=0.25,
        max_usd_healer=0.10,
    )
    assert cfg.max_usd_planner == 0.5


def test_llm_rate_limit_validates_range() -> None:
    LlmRateLimitConfig(requests_per_minute=120.0, capacity=100)
    with pytest.raises(ValidationError):
        LlmRateLimitConfig(requests_per_minute=0.0)
    with pytest.raises(ValidationError):
        LlmRateLimitConfig(requests_per_minute=10000.0)


def test_root_config_includes_llm_block() -> None:
    cfg = RootConfig(
        project={"name": "demo"},
        target={
            "base_url": "http://localhost:8080",
            "allowed_hosts": ["localhost"],
        },
    )
    assert isinstance(cfg.llm, LlmConfig)
    assert cfg.llm.default_provider == "null"
