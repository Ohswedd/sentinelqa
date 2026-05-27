"""Round-trip + invariant tests for every PRD §18.1 domain entity."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain import (
    ApiEndpoint,
    AuthBoundary,
    DiscoveryGraph,
    Element,
    Evidence,
    Finding,
    FindingLocation,
    Flow,
    FlowStep,
    Form,
    FormField,
    IdGenerator,
    ModuleResult,
    PolicyDecision,
    Project,
    QualityScore,
    RepairSuggestion,
    RiskMap,
    Route,
    RouteRisk,
    Target,
)

# `TestRun` / `TestCase` are domain entities; aliasing keeps pytest from
# treating them as test classes (they have constructors).
from engine.domain import TestCase as TestCaseModel
from engine.domain import TestRun as TestRunModel
from pydantic import ValidationError

GEN = IdGenerator()


def _make_finding(run_id: str | None = None) -> Finding:
    return Finding(
        id=GEN.new("FND"),
        run_id=run_id or GEN.new("RUN"),
        module="accessibility",
        category="a11y/missing-label",
        severity="medium",
        confidence=0.93,
        title="Button missing accessible name",
        description="A button on /dashboard has no accessible label.",
        location=FindingLocation(route="/dashboard", selector="button:nth-of-type(3)"),
        evidence=(
            Evidence(id=GEN.new("EVD"), type="screenshot", path=Path(".sentinel/a11y-004.png")),
        ),
        reproduction_steps=("Open /dashboard", "Inspect the icon-only button"),
        suggested_fix="Add aria-label or visible text.",
        affected_target="https://example.com/dashboard",
        recommendation="Add an aria-label to the button.",
        created_at=datetime.now(UTC),
    )


def test_project_round_trip() -> None:
    p = Project(name="example-app", root=Path("."), framework="nextjs", package_manager="pnpm")
    payload = p.to_dict()
    reparsed = Project.model_validate(payload)
    assert reparsed == p


def test_target_rejects_wildcards() -> None:
    with pytest.raises(ValidationError):
        Target(base_url="http://localhost:3000", allowed_hosts=["*.example.com"])


def test_target_freezes_allowed_hosts() -> None:
    t = Target(base_url="http://localhost:3000", allowed_hosts=["localhost", "127.0.0.1"])
    assert isinstance(t.allowed_hosts, frozenset)
    assert t.allowed_hosts == frozenset({"localhost", "127.0.0.1"})


def test_route_id_validated() -> None:
    rt = Route(id=GEN.new("RT"), path="/users", http_methods=frozenset({"GET", "POST"}))
    assert rt.path == "/users"
    with pytest.raises(ValidationError):
        Route(id="BAD-ID", path="/users")


def test_element_references_route() -> None:
    rt_id = GEN.new("RT")
    el = Element(
        id=GEN.new("EL"),
        role="button",
        accessible_name="Submit",
        selector="form > button[type=submit]",
        route_id=rt_id,
        tags=frozenset({"primary"}),
    )
    assert el.route_id == rt_id


def test_form_with_fields() -> None:
    f = Form(
        id=GEN.new("FRM"),
        action_url="https://example.com/login",
        method="POST",
        fields=(FormField(name="email", type="email", required=True),),
        submit_handler_present=True,
        validation_present=True,
    )
    assert len(f.fields) == 1
    assert f.fields[0].name == "email"


def test_api_endpoint() -> None:
    api = ApiEndpoint(
        id=GEN.new("API"),
        method="POST",
        path="/api/users",
        request_schema={"type": "object"},
        response_schema={"type": "object"},
        auth_strategy="bearer",
        source="openapi",
    )
    assert api.source == "openapi"


def test_flow_must_have_steps() -> None:
    with pytest.raises(ValidationError):
        Flow(id=GEN.new("FLW"), name="empty", steps=())


def test_flow_with_steps() -> None:
    fl = Flow(
        id=GEN.new("FLW"),
        name="login",
        steps=(
            FlowStep(description="visit /login", expected_outcome="form visible"),
            FlowStep(description="submit creds", expected_outcome="dashboard visible"),
        ),
        priority="P0",
        risk="critical",
    )
    assert len(fl.steps) == 2
    assert fl.priority == "P0"


def test_test_case_confidence_bounds() -> None:
    flow_id = GEN.new("FLW")
    tc = TestCaseModel(
        id=GEN.new("TC"),
        flow_id=flow_id,
        file_path=Path("tests/sentinel/login.spec.ts"),
        test_type="functional",
        confidence=0.8,
    )
    assert tc.flow_id == flow_id
    with pytest.raises(ValidationError):
        TestCaseModel(
            id=GEN.new("TC"),
            flow_id=flow_id,
            file_path=Path("tests/sentinel/x.spec.ts"),
            confidence=1.5,
        )


def test_test_run_requires_tz_aware_dt() -> None:
    target = Target(base_url="http://localhost:3000", allowed_hosts=["localhost"])
    with pytest.raises(ValidationError):
        TestRunModel(
            id=GEN.new("RUN"),
            started_at=datetime(2026, 5, 27, 12, 0, 0),
            target=target,
            modules_run=(),
        )


def test_test_run_round_trip() -> None:
    target = Target(base_url="http://localhost:3000", allowed_hosts=["localhost"])
    run = TestRunModel(
        id=GEN.new("RUN"),
        started_at=datetime.now(UTC),
        target=target,
        modules_run=("functional", "a11y"),
        status="incomplete",
    )
    payload = run.to_dict()
    reparsed = TestRunModel.model_validate(payload)
    assert reparsed.modules_run == run.modules_run


def test_module_result_sorts_findings_in_dict() -> None:
    r1 = _make_finding()
    r2 = _make_finding(run_id=r1.run_id)
    mr = ModuleResult(
        id=GEN.new("MOD"),
        name="accessibility",
        status="failed",
        findings=(r2, r1),
        metrics={"violations": 2},
        duration_ms=42,
    )
    dumped = mr.to_dict()
    ids_in_order = [f["id"] for f in dumped["findings"]]
    assert ids_in_order == sorted(ids_in_order)


def test_finding_matches_prd_18_2() -> None:
    f = _make_finding()
    payload = f.to_dict()
    # PRD §18.2 required keys.
    for key in ("id", "module", "severity", "title", "description", "evidence"):
        assert key in payload


def test_finding_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        Finding(
            id=GEN.new("FND"),
            run_id=GEN.new("RUN"),
            module="x",
            category="x",
            severity="info",
            confidence=0.5,
            title="t",
            description="d",
            created_at=datetime(2026, 1, 1),
        )


def test_quality_score_rejects_negative_component() -> None:
    with pytest.raises(ValidationError):
        QualityScore(
            id=GEN.new("SCR"),
            run_id=GEN.new("RUN"),
            total=90,
            components={"functional": -1.0},
        )


def test_policy_decision_blocking() -> None:
    pd = PolicyDecision(
        id=GEN.new("PD"),
        run_id=GEN.new("RUN"),
        release_decision="blocked",
        blocked_by=("critical-finding-1",),
        reasons=("1 critical finding present",),
    )
    assert pd.release_decision == "blocked"


def test_repair_suggestion_requires_review_by_default() -> None:
    rs = RepairSuggestion(
        id=GEN.new("RPR"),
        target_test="tests/sentinel/login.spec.ts",
        original="getByRole('button', { name: /submit/i })",
        proposed="getByTestId('submit')",
        confidence=0.6,
        reason="role-based locator broke after redesign",
    )
    assert rs.requires_human_review is True


def test_discovery_graph_assembly() -> None:
    rt = Route(id=GEN.new("RT"), path="/dashboard", auth_required=True)
    dg = DiscoveryGraph(
        id=GEN.new("DG"),
        routes=(rt,),
        elements=(),
        forms=(),
        api_endpoints=(),
        auth_boundaries=(AuthBoundary(route_id=rt.id, required_role="user"),),
    )
    assert len(dg.routes) == 1
    assert dg.auth_boundaries[0].route_id == rt.id


def test_risk_map() -> None:
    rt_id = GEN.new("RT")
    rm = RiskMap(
        id=GEN.new("RM"),
        entries=(RouteRisk(route_id=rt_id, score=0.7, justifications=("admin-only",)),),
    )
    assert rm.entries[0].score == pytest.approx(0.7)


def test_extra_keys_forbidden() -> None:
    with pytest.raises(ValidationError):
        Target.model_validate(
            {
                "base_url": "http://localhost:3000",
                "allowed_hosts": ["localhost"],
                "mode": "safe",
                "evil_extra": True,
            }
        )


def test_models_are_frozen() -> None:
    t = Target(base_url="http://localhost:3000", allowed_hosts=["localhost"])
    with pytest.raises(ValidationError):
        # frozen=True; attribute assignment is rejected
        t.mode = "authorized_destructive"


def test_finding_serializes_via_json() -> None:
    f = _make_finding()
    s = json.dumps(f.to_dict())
    payload = json.loads(s)
    assert payload["id"] == f.id
