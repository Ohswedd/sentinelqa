"""Null LLM adapter tests (task 06.04)."""

from __future__ import annotations

from engine.config.schema import PlannerLlmConfig
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.ids import IdGenerator
from engine.domain.test_plan import TestPlan
from engine.planner.llm_adapter import (
    NullLlmPlanner,
    build_llm_planner,
)


def _empty_plan(ids: IdGenerator) -> TestPlan:
    return TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://localhost/",
    )


def test_null_adapter_returns_no_proposals(deterministic_ids: IdGenerator) -> None:
    adapter = NullLlmPlanner()
    graph = DiscoveryGraph(id=deterministic_ids.new("DG"))
    plan = _empty_plan(deterministic_ids)
    assert adapter.propose_flows(graph, plan, id_generator=deterministic_ids) == ()
    assert adapter.usage.requests == 0


def test_factory_returns_null_when_disabled() -> None:
    cfg = PlannerLlmConfig(enabled=False, provider="openai", api_key_env="X")
    assert build_llm_planner(cfg).name == "null"


def test_factory_returns_null_when_provider_unset() -> None:
    cfg = PlannerLlmConfig(enabled=True, provider="null")
    assert build_llm_planner(cfg).name == "null"
