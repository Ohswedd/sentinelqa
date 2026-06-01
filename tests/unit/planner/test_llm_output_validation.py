"""LLM output validation tests."""

from __future__ import annotations

import pytest
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.ids import IdGenerator
from engine.domain.route import Route
from engine.planner.llm_adapter import (
    parse_provider_response,
    proposals_to_flows,
)


def test_parse_rejects_non_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_provider_response("not json at all")


def test_parse_rejects_extra_fields() -> None:
    with pytest.raises(ValueError, match="locked envelope"):
        parse_provider_response('{"flows": [], "rogue_field": 1}')


def test_parse_rejects_malformed_flow() -> None:
    body = '{"flows": [' '{"name": "", "steps": [], "priority": "P1", "risk": "high"}' "]}"
    with pytest.raises(ValueError, match="locked envelope"):
        parse_provider_response(body)


def test_parse_accepts_minimal_valid_flow() -> None:
    body = (
        '{"flows": ['
        '{"name": "x", "priority": "P1", "risk": "high", '
        '"confidence": 0.6, "steps": ['
        '{"description": "step", "expected_outcome": "ok"}'
        "]}"
        "]}"
    )
    flows = parse_provider_response(body)
    assert len(flows) == 1
    assert flows[0].name == "x"


def test_proposals_drops_unknown_route(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    body = (
        '{"flows": ['
        '{"name": "y", "priority": "P1", "risk": "high", '
        '"confidence": 0.6, "target_route_path": "/nope", '
        '"steps": [{"description": "s", "expected_outcome": "ok"}]}'
        "]}"
    )
    proposals = parse_provider_response(body)
    graph = DiscoveryGraph(
        id=ids.new("DG"),
        routes=(Route(id=ids.new("RT"), path="/"),),
    )
    flows = proposals_to_flows(
        proposals,
        graph=graph,
        id_generator=ids,
        existing_names=frozenset(),
    )
    assert flows == ()


def test_proposals_drops_duplicate_name(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    body = (
        '{"flows": ['
        '{"name": "login", "priority": "P0", "risk": "critical", '
        '"confidence": 0.9, "steps": ['
        '{"description": "s", "expected_outcome": "ok"}]}'
        "]}"
    )
    proposals = parse_provider_response(body)
    graph = DiscoveryGraph(id=ids.new("DG"))
    flows = proposals_to_flows(
        proposals,
        graph=graph,
        id_generator=ids,
        existing_names=frozenset({"login"}),
    )
    assert flows == ()


def test_proposals_accepts_unique_flow(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    body = (
        '{"flows": ['
        '{"name": "magic link", "priority": "P1", "risk": "high", '
        '"confidence": 0.7, "steps": ['
        '{"description": "click", "expected_outcome": "logged in"}]}'
        "]}"
    )
    proposals = parse_provider_response(body)
    graph = DiscoveryGraph(id=ids.new("DG"))
    flows = proposals_to_flows(
        proposals,
        graph=graph,
        id_generator=ids,
        existing_names=frozenset(),
    )
    assert len(flows) == 1
    assert flows[0].source == "llm"
    assert "llm" in flows[0].tags
