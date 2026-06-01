"""Deterministic planner core tests."""

from __future__ import annotations

import pytest
from engine.config.schema import ProjectConfig, RootConfig, TargetConfig
from engine.domain.discovery_graph import AuthBoundary, DiscoveryGraph
from engine.domain.form import Form, FormField
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap, RouteRisk
from engine.domain.route import Route
from engine.planner.core import DeterministicPlanner, bucketed_risk, priority_for_risk


def _config() -> RootConfig:
    return RootConfig(
        project=ProjectConfig(name="ex"),
        target=TargetConfig(
            base_url="http://localhost:3000",
            allowed_hosts=("localhost",),
        ),
    )


def _build_graph(ids: IdGenerator) -> tuple[DiscoveryGraph, RiskMap]:
    login = Route(id=ids.new("RT"), path="/login")
    dashboard = Route(id=ids.new("RT"), path="/dashboard", auth_required=True)
    admin = Route(id=ids.new("RT"), path="/admin/users", auth_required=True)
    crud_detail = Route(id=ids.new("RT"), path="/api/items/[id]")
    form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/login",
        method="POST",
        fields=(
            FormField(name="email", type="email", required=True),
            FormField(name="password", type="password", required=True),
        ),
        submit_handler_present=True,
    )
    graph = DiscoveryGraph(
        id=ids.new("DG"),
        routes=(login, dashboard, admin, crud_detail),
        forms=(form,),
        auth_boundaries=(
            AuthBoundary(route_id=admin.id, required_role="admin"),
            AuthBoundary(route_id=dashboard.id, required_role="user"),
        ),
    )
    risk = RiskMap(
        id=ids.new("RM"),
        entries=(
            RouteRisk(route_id=login.id, score=0.85),
            RouteRisk(route_id=admin.id, score=0.95),
            RouteRisk(route_id=dashboard.id, score=0.5),
            RouteRisk(route_id=crud_detail.id, score=0.4),
        ),
    )
    return graph, risk


# ----------------------------------------------------------------------
# Helpers under test
# ----------------------------------------------------------------------


def test_bucketed_risk_thresholds() -> None:
    assert bucketed_risk(0.95) == "critical"
    assert bucketed_risk(0.80) == "critical"
    assert bucketed_risk(0.79) == "high"
    assert bucketed_risk(0.60) == "high"
    assert bucketed_risk(0.59) == "medium"
    assert bucketed_risk(0.30) == "medium"
    assert bucketed_risk(0.29) == "low"
    assert bucketed_risk(0.0) == "low"


def test_priority_for_risk() -> None:
    assert priority_for_risk("critical") == "P0"
    assert priority_for_risk("high") == "P1"
    assert priority_for_risk("medium") == "P2"
    assert priority_for_risk("low") == "P3"


# ----------------------------------------------------------------------
# Core planner behaviour
# ----------------------------------------------------------------------


def test_plan_emits_smoke_test_per_route(deterministic_ids: IdGenerator) -> None:
    graph, risk = _build_graph(deterministic_ids)
    out = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id=deterministic_ids.new("RUN")
    )
    smoke_flows = [f for f in out.plan.flows if f.extractor == "route.smoke"]
    # One smoke flow per route.
    assert len(smoke_flows) == len(graph.routes)
    assert all("smoke" in f.tags for f in smoke_flows)


def test_plan_assigns_priority_by_risk_bucket(deterministic_ids: IdGenerator) -> None:
    graph, risk = _build_graph(deterministic_ids)
    out = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id=deterministic_ids.new("RUN")
    )
    admin_smoke = next(
        f for f in out.plan.flows if f.extractor == "route.smoke" and "/admin/users" in f.name
    )
    assert admin_smoke.priority == "P0"
    assert admin_smoke.risk == "critical"


def test_plan_form_with_no_handler_is_flagged_llm_audit_candidate(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/contact")
    form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/contact",
        method="POST",
        fields=(FormField(name="message", type="textarea", required=True),),
        submit_handler_present=False,
    )
    graph = DiscoveryGraph(id=ids.new("DG"), routes=(rt,), forms=(form,))
    risk = RiskMap(id=ids.new("RM"), entries=(RouteRisk(route_id=rt.id, score=0.4),))
    out = DeterministicPlanner(id_generator=ids).plan(graph, risk, _config(), run_id=ids.new("RUN"))
    # The smoke flow for /contact must carry llm_audit_candidate.
    smoke = next(f for f in out.plan.flows if f.extractor == "route.smoke")
    assert "llm_audit_candidate" in smoke.tags
    # And the form submit flow must be routed to llm_audit instead of functional.
    form_flow = next(f for f in out.plan.flows if f.extractor == "form.submit")
    form_case = next(c for c in out.plan.test_cases if c.flow_id == form_flow.id)
    assert form_case.test_type == "llm_audit"
    assert form_case.module == "llm_audit"


def test_plan_auth_boundary_flow_for_protected_routes(
    deterministic_ids: IdGenerator,
) -> None:
    graph, risk = _build_graph(deterministic_ids)
    out = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id=deterministic_ids.new("RUN")
    )
    ab_flows = [f for f in out.plan.flows if f.extractor == "route.auth_boundary"]
    # /dashboard + /admin/users
    assert {f.name for f in ab_flows} == {
        "auth-boundary: /dashboard",
        "auth-boundary: /admin/users",
    }
    admin_ab = next(f for f in ab_flows if "/admin/users" in f.name)
    assert admin_ab.required_auth_role == "admin"


def test_plan_api_contract_per_endpoint(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/")
    from engine.domain.api_endpoint import ApiEndpoint

    api1 = ApiEndpoint(id=ids.new("API"), method="GET", path="/api/items")
    api2 = ApiEndpoint(id=ids.new("API"), method="POST", path="/api/items")
    graph = DiscoveryGraph(id=ids.new("DG"), routes=(rt,), api_endpoints=(api1, api2))
    risk = RiskMap(id=ids.new("RM"))
    out = DeterministicPlanner(id_generator=ids).plan(graph, risk, _config(), run_id=ids.new("RUN"))
    api_flows = [f for f in out.plan.flows if f.extractor == "api.contract"]
    assert len(api_flows) == 2
    api_cases = [c for c in out.plan.test_cases if c.test_type == "api"]
    assert len(api_cases) == 2
    assert all(c.module == "api" for c in api_cases)


def test_plan_is_deterministic(deterministic_ids: IdGenerator) -> None:
    graph, risk = _build_graph(deterministic_ids)
    plan_a = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id="RUN-AAAAAAAAAAAA"
    )
    # Same inputs + fresh counter → byte-identical plan structure (ignore IDs).
    deterministic_ids2 = type(deterministic_ids)()
    graph2, risk2 = _build_graph(deterministic_ids2)
    plan_b = DeterministicPlanner(id_generator=deterministic_ids2).plan(
        graph2, risk2, _config(), run_id="RUN-AAAAAAAAAAAA"
    )
    # Compare by (priority, risk, name, extractor) keys — IDs differ but
    # structure is identical.
    keys_a = [(f.priority, f.risk, f.name, f.extractor) for f in plan_a.plan.flows]
    keys_b = [(f.priority, f.risk, f.name, f.extractor) for f in plan_b.plan.flows]
    assert keys_a == keys_b


def test_plan_coverage_estimate_matches_test_cases(
    deterministic_ids: IdGenerator,
) -> None:
    graph, risk = _build_graph(deterministic_ids)
    out = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id=deterministic_ids.new("RUN")
    )
    total = sum(out.plan.coverage_estimate.by_module.values())
    assert total == out.plan.coverage_estimate.total
    assert total == len(out.plan.test_cases)


def test_plan_flows_ordered_by_priority(deterministic_ids: IdGenerator) -> None:
    graph, risk = _build_graph(deterministic_ids)
    out = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id=deterministic_ids.new("RUN")
    )
    priorities = [f.priority for f in out.plan.flows]
    assert priorities == sorted(priorities)


def test_plan_test_cases_are_attached_to_real_flows(
    deterministic_ids: IdGenerator,
) -> None:
    graph, risk = _build_graph(deterministic_ids)
    out = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id=deterministic_ids.new("RUN")
    )
    flow_ids = {f.id for f in out.plan.flows}
    for case in out.plan.test_cases:
        assert case.flow_id in flow_ids


def test_plan_empty_graph_emits_empty_plan(deterministic_ids: IdGenerator) -> None:
    graph = DiscoveryGraph(id=deterministic_ids.new("DG"))
    risk = RiskMap(id=deterministic_ids.new("RM"))
    out = DeterministicPlanner(id_generator=deterministic_ids).plan(
        graph, risk, _config(), run_id=deterministic_ids.new("RUN")
    )
    assert out.plan.flows == ()
    assert out.plan.test_cases == ()
    assert out.plan.coverage_estimate.total == 0


def test_plan_form_priority_bumps_for_sensitive_routes(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    pay = Route(id=ids.new("RT"), path="/checkout")
    form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/checkout",
        method="POST",
        fields=(FormField(name="card", type="text", required=True),),
        submit_handler_present=True,
    )
    graph = DiscoveryGraph(id=ids.new("DG"), routes=(pay,), forms=(form,))
    risk = RiskMap(
        id=ids.new("RM"),
        # Risk score is low, but the route hint forces P0.
        entries=(RouteRisk(route_id=pay.id, score=0.1),),
    )
    out = DeterministicPlanner(id_generator=ids).plan(graph, risk, _config(), run_id=ids.new("RUN"))
    form_flow = next(f for f in out.plan.flows if f.extractor == "form.submit")
    assert form_flow.priority == "P0"


@pytest.mark.parametrize(
    "method",
    ["GET", "POST", "PUT", "DELETE"],
)
def test_api_methods_round_trip(method: str, deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/")
    from engine.domain.api_endpoint import ApiEndpoint

    api = ApiEndpoint(id=ids.new("API"), method=method, path="/api/x")  # type: ignore[arg-type]
    graph = DiscoveryGraph(id=ids.new("DG"), routes=(rt,), api_endpoints=(api,))
    risk = RiskMap(id=ids.new("RM"))
    out = DeterministicPlanner(id_generator=ids).plan(graph, risk, _config(), run_id=ids.new("RUN"))
    api_flow = next(f for f in out.plan.flows if f.extractor == "api.contract")
    assert method in api_flow.name
