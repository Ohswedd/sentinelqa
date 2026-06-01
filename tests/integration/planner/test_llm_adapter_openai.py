"""OpenAI planner adapter integration tests.

Uses a stub :class:`httpx.MockTransport` instead of any vendor SDK. The
adapter never reaches the live API in CI; the only failure modes we
exercise here are response shapes (good, malformed, budget-exceeded).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from engine.config.schema import PlannerLlmConfig
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.ids import IdGenerator
from engine.domain.route import Route
from engine.domain.test_plan import TestPlan
from engine.planner.llm_adapter import BudgetExceededError
from engine.planner.llm_providers._base import ProviderConfigError
from engine.planner.llm_providers.openai_planner import OpenAiLlmPlanner


class _CountingIdGenerator(IdGenerator):
    def __init__(self) -> None:
        self._counter = 0

    def _random_slug(self) -> str:
        self._counter += 1
        body = f"{self._counter:08X}"
        return ("A" * (12 - len(body))) + body


def _ids() -> IdGenerator:
    return _CountingIdGenerator()


def _empty_plan(ids: IdGenerator) -> TestPlan:
    return TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://localhost/",
    )


def _graph(ids: IdGenerator) -> DiscoveryGraph:
    return DiscoveryGraph(
        id=ids.new("DG"),
        routes=(Route(id=ids.new("RT"), path="/dashboard"),),
    )


def _config(api_key_env: str = "FAKE_KEY") -> PlannerLlmConfig:
    return PlannerLlmConfig(
        enabled=True,
        provider="openai",
        model="gpt-test",
        api_key_env=api_key_env,
        max_proposals=3,
        max_usd_per_run=10.0,
    )


def _mock_response(
    content_obj: dict[str, Any], *, usage: dict[str, int] | None = None
) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": json.dumps(content_obj)}}],
        "usage": usage or {"prompt_tokens": 200, "completion_tokens": 100},
    }


def _stub_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_openai_adapter_merges_valid_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.openai.com"
        assert request.headers["Authorization"] == "Bearer sk-test"
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-test"
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json=_mock_response(
                {
                    "flows": [
                        {
                            "name": "magic link login",
                            "priority": "P1",
                            "risk": "high",
                            "confidence": 0.8,
                            "target_route_path": "/dashboard",
                            "steps": [
                                {
                                    "description": "click magic link",
                                    "expected_outcome": "session established",
                                }
                            ],
                            "tags": ["auth", "magic_link"],
                        }
                    ]
                }
            ),
        )

    ids = _ids()
    graph = _graph(ids)
    plan = _empty_plan(ids)
    transport = _stub_transport(handler)
    client = httpx.Client(transport=transport)
    adapter = OpenAiLlmPlanner(config=_config(), http_client=client)
    flows = adapter.propose_flows(graph, plan, id_generator=ids)
    assert len(flows) == 1
    assert flows[0].name == "magic link login"
    assert flows[0].source == "llm"
    assert adapter.usage.requests == 1
    assert adapter.usage.cost_usd > 0


def test_openai_adapter_drops_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "not json"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    ids = _ids()
    transport = _stub_transport(handler)
    client = httpx.Client(transport=transport)
    adapter = OpenAiLlmPlanner(config=_config(), http_client=client)
    flows = adapter.propose_flows(_graph(ids), _empty_plan(ids), id_generator=ids)
    assert flows == ()
    # Usage still gets recorded so the budget accounting is accurate.
    assert adapter.usage.requests == 1


def test_openai_adapter_requires_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FAKE_KEY", raising=False)
    ids = _ids()
    transport = _stub_transport(lambda r: httpx.Response(200, json={}))
    client = httpx.Client(transport=transport)
    adapter = OpenAiLlmPlanner(config=_config(), http_client=client)
    with pytest.raises(ProviderConfigError):
        adapter.propose_flows(_graph(ids), _empty_plan(ids), id_generator=ids)


def test_openai_adapter_refuses_when_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_KEY", "sk-test")
    cfg = PlannerLlmConfig(
        enabled=True,
        provider="openai",
        api_key_env="FAKE_KEY",
        max_proposals=10,
        max_usd_per_run=0.0001,
    )

    ids = _ids()
    transport = _stub_transport(lambda r: httpx.Response(200, json=_mock_response({"flows": []})))
    client = httpx.Client(transport=transport)
    adapter = OpenAiLlmPlanner(config=cfg, http_client=client)
    with pytest.raises(BudgetExceededError):
        adapter.propose_flows(_graph(ids), _empty_plan(ids), id_generator=ids)


def test_openai_adapter_caps_proposals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_KEY", "sk-test")
    flows_response = {
        "flows": [
            {
                "name": f"flow {i}",
                "priority": "P2",
                "risk": "medium",
                "confidence": 0.5,
                "target_route_path": "/dashboard",
                "steps": [{"description": "s", "expected_outcome": "ok"}],
            }
            for i in range(5)
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mock_response(flows_response))

    ids = _ids()
    transport = _stub_transport(handler)
    client = httpx.Client(transport=transport)
    cfg = _config()
    adapter = OpenAiLlmPlanner(config=cfg, http_client=client)
    flows = adapter.propose_flows(_graph(ids), _empty_plan(ids), id_generator=ids)
    assert len(flows) == cfg.max_proposals
