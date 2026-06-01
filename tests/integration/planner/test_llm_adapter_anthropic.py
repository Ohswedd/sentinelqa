"""Anthropic planner adapter integration tests."""

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
from engine.planner.llm_providers.anthropic_planner import AnthropicLlmPlanner


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


def _config() -> PlannerLlmConfig:
    return PlannerLlmConfig(
        enabled=True,
        provider="anthropic",
        api_key_env="ANTHROPIC_FAKE",
        model="claude-test",
        max_usd_per_run=10.0,
    )


def _mock_response(content_obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(content_obj)}],
        "usage": {"input_tokens": 150, "output_tokens": 50},
    }


def test_anthropic_adapter_translates_messages_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_FAKE", "anthropic-sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.anthropic.com"
        assert request.headers["x-api-key"] == "anthropic-sk-test"
        assert request.headers["anthropic-version"] == "2023-06-01"
        payload = json.loads(request.content)
        assert payload["model"] == "claude-test"
        assert payload["system"].startswith("# Planner LLM prompt")
        return httpx.Response(
            200,
            json=_mock_response(
                {
                    "flows": [
                        {
                            "name": "session expiry probe",
                            "priority": "P2",
                            "risk": "medium",
                            "confidence": 0.6,
                            "target_route_path": "/dashboard",
                            "steps": [
                                {
                                    "description": "expire cookie",
                                    "expected_outcome": "redirected to login",
                                }
                            ],
                        }
                    ]
                }
            ),
        )

    ids = _ids()
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = AnthropicLlmPlanner(config=_config(), http_client=client)
    flows = adapter.propose_flows(_graph(ids), _empty_plan(ids), id_generator=ids)
    assert len(flows) == 1
    assert flows[0].source == "llm"


def test_anthropic_adapter_handles_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_FAKE", "anthropic-sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [], "usage": {"input_tokens": 1, "output_tokens": 1}},
        )

    ids = _ids()
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = AnthropicLlmPlanner(config=_config(), http_client=client)
    flows = adapter.propose_flows(_graph(ids), _empty_plan(ids), id_generator=ids)
    assert flows == ()
