"""End-to-end test: discovery graph → planner → generator → files on disk."""

from __future__ import annotations

from pathlib import Path

from engine.config.schema import RootConfig
from engine.domain.discovery_graph import AuthBoundary, DiscoveryGraph
from engine.domain.element import Element
from engine.domain.form import Form, FormField
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap, RouteRisk
from engine.domain.route import Route
from engine.generator import (
    GenerationInputs,
    GenerationOptions,
    GeneratorPipeline,
    write_generated_files,
)
from engine.planner.core import DeterministicPlanner


def _build_demo(ids: IdGenerator) -> tuple[DiscoveryGraph, RiskMap, RootConfig]:
    home = Route(id=ids.new("RT"), path="/", http_methods=frozenset({"GET"}))
    login = Route(id=ids.new("RT"), path="/login", http_methods=frozenset({"GET", "POST"}))
    admin = Route(id=ids.new("RT"), path="/admin", auth_required=True)
    graph = DiscoveryGraph(
        id=ids.new("DG"),
        routes=(home, login, admin),
        elements=(
            Element(
                id=ids.new("EL"),
                role="heading",
                accessible_name="Welcome",
                selector="h1",
                route_id=home.id,
            ),
            Element(
                id=ids.new("EL"),
                role="link",
                accessible_name="Home",
                selector="a",
                route_id=home.id,
            ),
            Element(
                id=ids.new("EL"),
                role="textbox",
                accessible_name="Email",
                selector="#e",
                route_id=login.id,
            ),
            Element(
                id=ids.new("EL"),
                role="textbox",
                accessible_name="Password",
                selector="#p",
                route_id=login.id,
            ),
            Element(
                id=ids.new("EL"),
                role="button",
                accessible_name="Sign in",
                selector="b",
                route_id=login.id,
            ),
        ),
        forms=(
            Form(id=ids.new("FRM"), method="POST", fields=(FormField(name="email", type="email"),)),
        ),
        api_endpoints=(),
        auth_boundaries=(AuthBoundary(route_id=admin.id, required_role="admin"),),
    )
    risk = RiskMap(
        id=ids.new("RM"),
        entries=(
            RouteRisk(route_id=home.id, score=0.2, justifications=()),
            RouteRisk(route_id=login.id, score=0.9, justifications=("login",)),
            RouteRisk(route_id=admin.id, score=0.85, justifications=("admin",)),
        ),
    )
    config = RootConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "project": {"name": "demo"},
            "target": {"base_url": "http://localhost:3000/", "allowed_hosts": ["localhost"]},
            "security": {"mode": "safe"},
        }
    )
    return graph, risk, config


def test_pipeline_produces_specs_pageobjects_and_plan_md(tmp_path: Path) -> None:
    ids = IdGenerator()
    graph, risk, config = _build_demo(ids)
    plan = (
        DeterministicPlanner(id_generator=ids).plan(graph, risk, config, run_id=ids.new("RUN")).plan
    )

    result = GeneratorPipeline().generate(
        GenerationInputs(
            plan=plan,
            graph=graph,
            out_dir=tmp_path,
            options=GenerationOptions(base_url="http://localhost:3000/"),
        )
    )

    kinds = {f.kind for f in result.files}
    assert kinds >= {"spec", "page-object", "plan-md"}
    assert len(result.page_objects) >= 2  # /login + /admin (3 elements) → at least 2 page objs

    # Banners present.
    for f in result.files:
        assert "SentinelQA Generated" in f.content

    # Write files atomically.
    outcomes = write_generated_files([(f.path, f.content) for f in result.files])
    assert all(o.status in {"written", "unchanged"} for o in outcomes)
    # Re-running is idempotent: a second pass yields all `unchanged`.
    second = write_generated_files([(f.path, f.content) for f in result.files])
    assert all(o.status == "unchanged" for o in second)


def test_pipeline_diff_section_after_regeneration(tmp_path: Path) -> None:
    ids = IdGenerator()
    graph, risk, config = _build_demo(ids)
    plan = (
        DeterministicPlanner(id_generator=ids).plan(graph, risk, config, run_id=ids.new("RUN")).plan
    )
    pipeline = GeneratorPipeline()
    out = pipeline.generate(GenerationInputs(plan=plan, graph=graph, out_dir=tmp_path))
    write_generated_files([(f.path, f.content) for f in out.files])
    plan_md = out.plan_md_path
    assert plan_md.exists()
    body = plan_md.read_text(encoding="utf-8")
    # Spec list rendered.
    assert "### Specs" in body


def test_refuses_to_overwrite_hand_edited_spec(tmp_path: Path) -> None:
    ids = IdGenerator()
    graph, risk, config = _build_demo(ids)
    plan = (
        DeterministicPlanner(id_generator=ids).plan(graph, risk, config, run_id=ids.new("RUN")).plan
    )
    result = GeneratorPipeline().generate(
        GenerationInputs(plan=plan, graph=graph, out_dir=tmp_path)
    )
    spec_file = next(f for f in result.files if f.kind == "spec")
    spec_file.path.parent.mkdir(parents=True, exist_ok=True)
    spec_file.path.write_text("// HAND EDITED\n", encoding="utf-8")

    import pytest
    from engine.generator import OverwriteError

    with pytest.raises(OverwriteError):
        write_generated_files([(spec_file.path, spec_file.content)])

    # --force overrides.
    write_generated_files([(spec_file.path, spec_file.content)], force=True)
    assert "SentinelQA Generated" in spec_file.path.read_text(encoding="utf-8")
