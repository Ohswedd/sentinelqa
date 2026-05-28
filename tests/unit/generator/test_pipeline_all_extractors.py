"""Exercise every per-extractor renderer in :class:`GeneratorPipeline`.

The deterministic planner only emits a subset of flow extractors in any
given run (it picks based on the discovery graph). To get the
generator's per-extractor branches covered we hand-craft a synthetic
plan containing one flow per renderer path.
"""

from __future__ import annotations

from pathlib import Path

from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.flow import Flow, FlowStep
from engine.domain.ids import IdGenerator
from engine.domain.route import Route
from engine.domain.test_case import TestCase
from engine.domain.test_plan import CoverageEstimate, TestPlan
from engine.generator import GenerationInputs, GeneratorPipeline


def _flow(ids: IdGenerator, *, name: str, extractor: str, route_id: str | None = None) -> Flow:
    steps = (
        FlowStep(
            description="go",
            target_route_id=route_id,
            expected_outcome="ok",
        ),
    )
    return Flow(
        id=ids.new("FLW"),
        name=name,
        steps=steps,
        priority="P1",
        risk="medium",
        confidence=0.95,
        extractor=extractor,
        source="deterministic",
        tags=("test",),
    )


EXTRACTORS = [
    "route.smoke",
    "route.auth_boundary",
    "form.submit",
    "login",
    "signup",
    "logout",
    "password_reset",
    "crud",
    "admin",
    "role",
    "payment_sandbox",
    "file_upload_download",
    "api.contract",
    "a11y",
    "perf",
    "unknown_kind",  # falls back to smoke
]


def test_every_extractor_renders_a_spec(tmp_path: Path) -> None:
    ids = IdGenerator()
    home = Route(id=ids.new("RT"), path="/")
    flows = []
    for ext in EXTRACTORS:
        # The api.contract renderer parses the flow name for "<METHOD> <PATH>"
        # so give it the canonical format.
        name = "api contract: GET /api/users" if ext == "api.contract" else f"{ext}: demo"
        flows.append(_flow(ids, name=name, extractor=ext, route_id=home.id))

    plan = TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://localhost:3000/",
        flows=tuple(flows),
        test_cases=tuple(
            TestCase(id=ids.new("TC"), flow_id=f.id, file_path=Path(f"sentinel/{f.id}.spec.ts"))
            for f in flows
        ),
        coverage_estimate=CoverageEstimate(by_module={"functional": len(flows)}, total=len(flows)),
    )
    graph = DiscoveryGraph(id=plan.discovery_graph_id, routes=(home,))

    result = GeneratorPipeline().generate(
        GenerationInputs(plan=plan, graph=graph, out_dir=tmp_path)
    )
    specs = [f for f in result.files if f.kind == "spec"]
    assert len(specs) == len(EXTRACTORS)
    for spec in specs:
        assert "SentinelQA Generated" in spec.content
        assert "test.describe" in spec.content or "test.describe(" in spec.content


def test_api_contract_uses_post_when_name_says_so(tmp_path: Path) -> None:
    ids = IdGenerator()
    home = Route(id=ids.new("RT"), path="/")
    flow = _flow(ids, name="api contract: POST /api/users", extractor="api.contract")
    plan = TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://localhost:3000/",
        flows=(flow,),
        test_cases=(
            TestCase(id=ids.new("TC"), flow_id=flow.id, file_path=Path("sentinel/x.spec.ts")),
        ),
    )
    graph = DiscoveryGraph(id=plan.discovery_graph_id, routes=(home,))
    result = GeneratorPipeline().generate(
        GenerationInputs(plan=plan, graph=graph, out_dir=tmp_path)
    )
    [spec] = (f for f in result.files if f.kind == "spec")
    assert '"POST"' in spec.content
    # POST expected status set includes 201/204.
    assert "201" in spec.content


def test_role_boundary_uses_required_auth_role(tmp_path: Path) -> None:
    ids = IdGenerator()
    home = Route(id=ids.new("RT"), path="/admin", auth_required=True)
    flow = Flow(
        id=ids.new("FLW"),
        name="role: editor",
        steps=(FlowStep(description="go", target_route_id=home.id, expected_outcome="ok"),),
        priority="P1",
        risk="high",
        confidence=0.9,
        extractor="role",
        required_auth_role="editor",
        source="deterministic",
        tags=(),
    )
    plan = TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://localhost:3000/",
        flows=(flow,),
        test_cases=(
            TestCase(id=ids.new("TC"), flow_id=flow.id, file_path=Path("sentinel/x.spec.ts")),
        ),
    )
    graph = DiscoveryGraph(id=plan.discovery_graph_id, routes=(home,))
    result = GeneratorPipeline().generate(
        GenerationInputs(plan=plan, graph=graph, out_dir=tmp_path)
    )
    [spec] = (f for f in result.files if f.kind == "spec")
    assert "editor" in spec.content
