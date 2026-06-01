"""Plan writer unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.config.schema import ProjectConfig, RootConfig, TargetConfig
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap, RouteRisk
from engine.domain.route import Route
from engine.domain.test_plan import TestPlan
from engine.planner.core import DeterministicPlanner
from engine.planner.plan_writer import read_plan, write_plan_artifacts


def _config() -> RootConfig:
    return RootConfig(
        project=ProjectConfig(name="ex"),
        target=TargetConfig(
            base_url="http://localhost:3000",
            allowed_hosts=("localhost",),
        ),
    )


def _build_plan(ids: IdGenerator) -> TestPlan:
    rt = Route(id=ids.new("RT"), path="/login")
    rt2 = Route(id=ids.new("RT"), path="/dashboard", auth_required=True)
    graph = DiscoveryGraph(id=ids.new("DG"), routes=(rt, rt2))
    risk = RiskMap(
        id=ids.new("RM"),
        entries=(
            RouteRisk(route_id=rt.id, score=0.9),
            RouteRisk(route_id=rt2.id, score=0.4),
        ),
    )
    out = DeterministicPlanner(id_generator=ids).plan(graph, risk, _config(), run_id=ids.new("RUN"))
    return out.plan


def test_writer_emits_plan_json_with_schema_envelope(
    deterministic_ids: IdGenerator, tmp_path: Path
) -> None:
    plan = _build_plan(deterministic_ids)
    written = write_plan_artifacts(plan=plan, out_dir=tmp_path)
    assert (tmp_path / "plan.json").exists()
    payload = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert payload["plan"]["id"].startswith("PLN-")
    assert written["plan_json"] == tmp_path / "plan.json"


def test_writer_emits_plan_md(deterministic_ids: IdGenerator, tmp_path: Path) -> None:
    plan = _build_plan(deterministic_ids)
    write_plan_artifacts(plan=plan, out_dir=tmp_path)
    md = (tmp_path / "plan.md").read_text(encoding="utf-8")
    assert md.startswith("# Test plan")
    assert "Coverage estimate" in md
    assert f"`{plan.id}`" in md


def test_writer_round_trip_through_read_plan(
    deterministic_ids: IdGenerator, tmp_path: Path
) -> None:
    plan = _build_plan(deterministic_ids)
    write_plan_artifacts(plan=plan, out_dir=tmp_path)
    reparsed = read_plan(tmp_path / "plan.json")
    assert reparsed == plan


def test_writer_output_is_byte_stable(deterministic_ids: IdGenerator, tmp_path: Path) -> None:
    plan = _build_plan(deterministic_ids)
    write_plan_artifacts(plan=plan, out_dir=tmp_path / "a")
    write_plan_artifacts(plan=plan, out_dir=tmp_path / "b")
    a = (tmp_path / "a" / "plan.json").read_bytes()
    b = (tmp_path / "b" / "plan.json").read_bytes()
    assert a == b
    am = (tmp_path / "a" / "plan.md").read_bytes()
    bm = (tmp_path / "b" / "plan.md").read_bytes()
    assert am == bm


def test_read_plan_rejects_missing_plan_key(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "1"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'plan' key"):
        read_plan(path)


def test_writer_empty_plan_md_renders(deterministic_ids: IdGenerator, tmp_path: Path) -> None:
    ids = deterministic_ids
    plan = TestPlan(
        id=ids.new("PLN"),
        run_id=ids.new("RUN"),
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://localhost:3000/",
    )
    write_plan_artifacts(plan=plan, out_dir=tmp_path)
    md = (tmp_path / "plan.md").read_text(encoding="utf-8")
    assert "_No test cases planned._" in md
    assert "_No flows planned._" in md
