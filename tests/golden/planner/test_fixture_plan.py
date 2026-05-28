"""Golden plan for the canonical fixture app (task 06.01 + 06.03).

Locks the planner output for a representative DiscoveryGraph + RiskMap.
A drift here means the planner changed observably; reviewers should
inspect the diff and update the golden via the standard
``SENTINELQA_UPDATE_GOLDENS=1`` workflow.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from engine.config.schema import ProjectConfig, RootConfig, TargetConfig
from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.discovery_graph import AuthBoundary, DiscoveryGraph
from engine.domain.form import Form, FormField
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap, RouteRisk
from engine.domain.route import Route
from engine.planner.core import DeterministicPlanner
from engine.planner.plan_writer import write_plan_artifacts

GOLDEN_DIR = Path(__file__).parent / "fixtures"


class _CountingIdGenerator(IdGenerator):
    def __init__(self) -> None:
        self._counter = 0

    def _random_slug(self) -> str:
        self._counter += 1
        body = f"{self._counter:08X}"
        return ("A" * (12 - len(body))) + body


def _build_fixture_graph() -> tuple[DiscoveryGraph, RiskMap, RootConfig, str]:
    ids = _CountingIdGenerator()
    home = Route(id=ids.new("RT"), path="/")
    login = Route(id=ids.new("RT"), path="/login")
    signup = Route(id=ids.new("RT"), path="/signup")
    dashboard = Route(id=ids.new("RT"), path="/dashboard", auth_required=True)
    admin = Route(id=ids.new("RT"), path="/admin/users", auth_required=True)
    items_list = Route(id=ids.new("RT"), path="/api/items")
    items_detail = Route(id=ids.new("RT"), path="/api/items/[id]")
    checkout = Route(id=ids.new("RT"), path="/checkout/stripe")
    upload = Route(id=ids.new("RT"), path="/uploads")
    verify = Route(id=ids.new("RT"), path="/verify/[token]")

    login_form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/login",
        method="POST",
        fields=(
            FormField(name="email", type="email", required=True),
            FormField(name="password", type="password", required=True),
        ),
        submit_handler_present=True,
    )
    contact_form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/uploads",
        method="POST",
        fields=(
            FormField(name="message", type="textarea", required=True),
            FormField(name="document", type="file", required=False),
        ),
        submit_handler_present=False,
    )

    api_get = ApiEndpoint(id=ids.new("API"), method="GET", path="/api/items")
    api_post = ApiEndpoint(id=ids.new("API"), method="POST", path="/api/items")
    api_delete = ApiEndpoint(id=ids.new("API"), method="DELETE", path="/api/items/[id]")

    graph = DiscoveryGraph(
        id=ids.new("DG"),
        routes=(
            home,
            login,
            signup,
            dashboard,
            admin,
            items_list,
            items_detail,
            checkout,
            upload,
            verify,
        ),
        forms=(login_form, contact_form),
        api_endpoints=(api_get, api_post, api_delete),
        auth_boundaries=(
            AuthBoundary(route_id=dashboard.id, required_role="user"),
            AuthBoundary(route_id=admin.id, required_role="admin"),
        ),
    )
    risk = RiskMap(
        id=ids.new("RM"),
        entries=(
            RouteRisk(route_id=home.id, score=0.1, justifications=("public",)),
            RouteRisk(route_id=login.id, score=0.85, justifications=("auth surface",)),
            RouteRisk(route_id=signup.id, score=0.7, justifications=("user input",)),
            RouteRisk(route_id=dashboard.id, score=0.55, justifications=("authenticated",)),
            RouteRisk(route_id=admin.id, score=0.95, justifications=("admin",)),
            RouteRisk(route_id=items_list.id, score=0.3),
            RouteRisk(route_id=items_detail.id, score=0.4),
            RouteRisk(route_id=checkout.id, score=0.6),
            RouteRisk(route_id=upload.id, score=0.5),
            RouteRisk(route_id=verify.id, score=0.4),
        ),
    )
    cfg = RootConfig(
        project=ProjectConfig(name="fixture-app"),
        target=TargetConfig(
            base_url="http://localhost:3000",
            allowed_hosts=("localhost",),
        ),
    )
    return graph, risk, cfg, ids.new("RUN")


@pytest.fixture
def fixture_plan_payload(tmp_path: Path) -> str:
    graph, risk, cfg, run_id = _build_fixture_graph()
    # Reset counter to keep IDs stable across the planner's own ID needs.
    planner = DeterministicPlanner(id_generator=_CountingIdGenerator())
    # Patch the planner's counter so the only IDs produced are PLN, FLW, TC.
    # The graph above already consumed counters 1..N from its own generator,
    # so we feed the planner its own generator and reset the run_id to a
    # stable string.
    out = planner.plan(graph, risk, cfg, run_id="RUN-AAAAAAAAAAAA")
    write_plan_artifacts(plan=out.plan, out_dir=tmp_path)
    return (tmp_path / "plan.json").read_text(encoding="utf-8")


def _golden_path() -> Path:
    return GOLDEN_DIR / "fixture-app.plan.json"


def test_fixture_plan_matches_golden(fixture_plan_payload: str) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden = _golden_path()
    if os.environ.get("SENTINELQA_UPDATE_GOLDENS"):
        golden.write_text(fixture_plan_payload, encoding="utf-8")
    if not golden.exists():
        pytest.fail(
            f"{golden} missing — run `SENTINELQA_UPDATE_GOLDENS=1 pytest tests/golden/planner` "
            "to create it."
        )
    expected = golden.read_text(encoding="utf-8")
    assert fixture_plan_payload == expected


def test_fixture_plan_round_trips(fixture_plan_payload: str) -> None:
    from engine.domain.test_plan import TestPlan

    payload = json.loads(fixture_plan_payload)
    plan = TestPlan.model_validate(payload["plan"])
    assert plan.id.startswith("PLN-")
    assert plan.target_url == "http://localhost:3000/"
    assert payload["schema_version"] == "1"
