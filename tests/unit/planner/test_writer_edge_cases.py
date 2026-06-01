"""Edge-case tests for plan_writer + LLM adapter helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from engine.config.schema import PlannerLlmConfig
from engine.planner.llm_adapter import (
    PROMPT_VERSION,
    BudgetExceededError,
    build_graph_summary,
    build_llm_planner,
    ensure_within_budget,
    load_locked_prompt,
)
from engine.planner.llm_providers._base import (
    HttpLlmProviderBase,
    ProviderConfigError,
)
from engine.planner.plan_writer import _to_jsonable

# ----------------------------------------------------------------------
# _to_jsonable fallback branches
# ----------------------------------------------------------------------


@dataclass
class _Sample:
    a: int
    b: str


def test_to_jsonable_handles_dataclass() -> None:
    out = _to_jsonable(_Sample(a=1, b="x"))
    assert out == {"a": 1, "b": "x"}


def test_to_jsonable_handles_path() -> None:
    p = Path("/tmp/example.txt")
    assert _to_jsonable(p) == str(p)


def test_to_jsonable_handles_none_and_scalars() -> None:
    assert _to_jsonable(None) is None
    assert _to_jsonable(1) == 1
    assert _to_jsonable(True) is True
    assert _to_jsonable(1.5) == 1.5
    assert _to_jsonable("x") == "x"


def test_to_jsonable_unknown_type_stringifies() -> None:
    class _Mystery:
        def __str__(self) -> str:
            return "mystery"

    assert _to_jsonable(_Mystery()) == "mystery"


def test_to_jsonable_set_is_sorted() -> None:
    out = _to_jsonable({"b", "a", "c"})
    assert out == ["a", "b", "c"]


# ----------------------------------------------------------------------
# LLM helper coverage
# ----------------------------------------------------------------------


def test_load_locked_prompt_returns_versioned_text() -> None:
    body = load_locked_prompt()
    assert PROMPT_VERSION in "1"
    assert "Planner LLM prompt" in body


def test_build_graph_summary_excludes_secrets(deterministic_ids) -> None:
    from engine.domain.discovery_graph import DiscoveryGraph
    from engine.domain.route import Route
    from engine.domain.test_plan import TestPlan

    ids = deterministic_ids
    graph = DiscoveryGraph(
        id=ids.new("DG"),
        routes=(Route(id=ids.new("RT"), path="/x"),),
    )
    plan = TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=graph.id,
        risk_map_id=ids.new("RM"),
        target_url="http://localhost/",
    )
    summary = build_graph_summary(graph, plan)
    assert summary["routes"] == [{"path": "/x", "auth_required": False}]
    assert "existing_flow_names" in summary
    # Round-trip is JSON-serializable.
    json.dumps(summary)


# ----------------------------------------------------------------------
# Provider factory branches
# ----------------------------------------------------------------------


def test_build_llm_planner_constructs_openai() -> None:
    cfg = PlannerLlmConfig(enabled=True, provider="openai", api_key_env="K")
    adapter = build_llm_planner(cfg)
    assert adapter.name == "openai"


def test_build_llm_planner_constructs_anthropic() -> None:
    cfg = PlannerLlmConfig(enabled=True, provider="anthropic", api_key_env="K")
    adapter = build_llm_planner(cfg)
    assert adapter.name == "anthropic"


# ----------------------------------------------------------------------
# Base provider error paths
# ----------------------------------------------------------------------


class _SubclassOnlyBase(HttpLlmProviderBase):
    """A subclass that doesn't override required hooks — exercises error paths."""

    name = "test"

    def endpoint_url(self) -> str:
        return "http://example.invalid/x"

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        return {"X-Api": api_key}

    def build_payload(self, *, prompt: str, graph_summary, max_proposals: int, model: str) -> dict:
        return {}

    def extract_response_text(self, body) -> str:
        return "{}"


def test_provider_skips_when_budget_already_exhausted(
    deterministic_ids, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.domain.discovery_graph import DiscoveryGraph
    from engine.domain.test_plan import TestPlan

    monkeypatch.setenv("K", "k")
    cfg = PlannerLlmConfig(enabled=True, provider="openai", api_key_env="K", max_usd_per_run=0.0)
    adapter = _SubclassOnlyBase(config=cfg)
    ids = deterministic_ids
    plan = TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://x/",
    )
    # No call needed; budget hits the hard-stop immediately.
    out = adapter.propose_flows(DiscoveryGraph(id=ids.new("DG")), plan, id_generator=ids)
    assert out == ()


def test_ensure_within_budget_passes_when_no_history() -> None:
    from engine.planner.llm_adapter import LlmUsage

    ensure_within_budget(usage=LlmUsage(), additional_cost=0.0, budget_usd=1.0)


def test_ensure_within_budget_raises_when_cumulative_exceeds() -> None:
    from engine.planner.llm_adapter import LlmUsage

    with pytest.raises(BudgetExceededError):
        ensure_within_budget(usage=LlmUsage(cost_usd=0.95), additional_cost=0.1, budget_usd=1.0)


def test_provider_requires_api_key_env_in_config(deterministic_ids) -> None:
    from engine.domain.discovery_graph import DiscoveryGraph
    from engine.domain.test_plan import TestPlan

    cfg = PlannerLlmConfig(
        enabled=True,
        provider="openai",
        api_key_env=None,
        max_usd_per_run=10.0,
    )
    adapter = _SubclassOnlyBase(config=cfg)
    ids = deterministic_ids
    plan = TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://x/",
    )
    with pytest.raises(ProviderConfigError):
        adapter.propose_flows(DiscoveryGraph(id=ids.new("DG")), plan, id_generator=ids)


# ----------------------------------------------------------------------
# OpenAI/Anthropic extract_response_text edge cases
# ----------------------------------------------------------------------


def test_openai_handles_empty_choices() -> None:
    from engine.planner.llm_providers.openai_planner import OpenAiLlmPlanner

    cfg = PlannerLlmConfig(enabled=True, provider="openai", api_key_env="K")
    adapter = OpenAiLlmPlanner(config=cfg)
    assert adapter.extract_response_text({"choices": []}) == "{}"


def test_openai_handles_non_string_content() -> None:
    from engine.planner.llm_providers.openai_planner import OpenAiLlmPlanner

    cfg = PlannerLlmConfig(enabled=True, provider="openai", api_key_env="K")
    adapter = OpenAiLlmPlanner(config=cfg)
    body = {"choices": [{"message": {"content": 42}}]}
    assert adapter.extract_response_text(body) == "{}"


def test_anthropic_handles_non_text_blocks() -> None:
    from engine.planner.llm_providers.anthropic_planner import AnthropicLlmPlanner

    cfg = PlannerLlmConfig(enabled=True, provider="anthropic", api_key_env="K")
    adapter = AnthropicLlmPlanner(config=cfg)
    body = {"content": [{"type": "tool_use"}]}
    assert adapter.extract_response_text(body) == "{}"
