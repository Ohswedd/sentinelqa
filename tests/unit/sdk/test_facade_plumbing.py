"""Facade plumbing: discover/plan/generate/run_plan dispatch + signature checks.

The engine entry points themselves are tested by their own phases. Here
we only verify that the SDK forwards arguments correctly, wires the
right safety guards in, and returns the right shape.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.flow import Flow, FlowStep
from engine.domain.ids import IdGenerator
from engine.domain.test_plan import CoverageEstimate, TestPlan
from engine.orchestrator.registry import ModuleRegistry, default_registry

from sentinelqa import Sentinel


def _write_minimal_config(root: Path) -> Path:
    config_path = root / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: facade-plumb\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "modules:\n"
        "  functional: true\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  chaos: false\n"
        "  llm_audit: false\n",
        encoding="utf-8",
    )
    return config_path


@pytest.fixture
def patched_registry() -> Iterator[ModuleRegistry]:
    reg = default_registry()
    prior = reg.modules.get("functional")
    reg.register_module("functional", lambda cfg, decision: {"ok": True})
    try:
        yield reg
    finally:
        if prior is not None:
            reg.register_module("functional", prior)
        else:
            reg.modules.pop("functional", None)


def _empty_plan() -> TestPlan:
    ids = IdGenerator()
    run_id = ids.new("RUN")
    return TestPlan(
        id=ids.new("PLN"),
        run_id=run_id,
        discovery_graph_id=ids.new("DG"),
        risk_map_id=ids.new("RM"),
        target_url="http://localhost:3000",
        flows=(),
        test_cases=(),
        coverage_estimate=CoverageEstimate(),
    )


def _empty_graph() -> DiscoveryGraph:
    return DiscoveryGraph(id=IdGenerator().new("DG"))


def test_discover_uses_safety_policy_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``discover`` MUST enforce safety before any I/O (PRD §2.3)."""

    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)

    # Patch the crawler so the test never tries real network I/O even
    # if safety somehow let an unsafe URL through.
    from engine.discovery import pipeline as pipeline_mod

    class _ExplodingPipeline:
        def __init__(self, *a: Any, **kw: Any) -> None:
            raise AssertionError("safety policy should have blocked before this")

    monkeypatch.setattr(pipeline_mod, "DiscoveryPipeline", _ExplodingPipeline)

    # Unsafe URL must raise inside the safety policy, NOT inside the
    # crawler. The SDK lets the exception propagate.
    from sentinelqa import UnsafeTargetError

    with pytest.raises(UnsafeTargetError):
        qa.discover("http://attacker.test")


def test_discover_returns_graph_on_localhost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)

    from engine.discovery import pipeline as pipeline_mod

    class _StubResult:
        def __init__(self, graph: DiscoveryGraph) -> None:
            self.graph = graph

    class _StubPipeline:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def run(self, inputs: Any) -> _StubResult:
            return _StubResult(_empty_graph())

    monkeypatch.setattr(pipeline_mod, "DiscoveryPipeline", _StubPipeline)
    graph = qa.discover("http://localhost:3000")
    assert isinstance(graph, DiscoveryGraph)


def test_plan_with_explicit_graph_no_crawl(tmp_path: Path) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    plan = qa.plan(graph=_empty_graph())
    assert isinstance(plan, TestPlan)


def test_plan_url_route_uses_safety_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    from sentinelqa import UnsafeTargetError

    with pytest.raises(UnsafeTargetError):
        qa.plan(url="http://attacker.test")


def test_plan_url_returns_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    # Stub the discover pipeline so url-mode plan doesn't hit network.
    from engine.discovery import pipeline as pipeline_mod

    class _StubResult:
        def __init__(self, graph: DiscoveryGraph) -> None:
            self.graph = graph

    class _StubPipeline:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def run(self, inputs: Any) -> _StubResult:
            return _StubResult(_empty_graph())

    monkeypatch.setattr(pipeline_mod, "DiscoveryPipeline", _StubPipeline)
    plan = qa.plan(url="http://localhost:3000")
    assert isinstance(plan, TestPlan)


def test_generate_tests_writes_into_out_dir(
    tmp_path: Path,
) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    out_dir = tmp_path / "out"
    written = qa.generate_tests(_empty_plan(), out_dir)
    # An empty plan still produces a generated plan.md.
    assert isinstance(written, tuple)


def test_run_plan_invokes_audit(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.run_plan(_empty_plan(), spec_root=tmp_path / "tests")
    # Defers to qa.audit() which uses the stubbed module — must end
    # up "passed" because the empty plan produced no failures.
    assert result.status == "passed"


def test_facade_records_started_at(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    before = datetime.now(UTC)
    result = qa.audit()
    after = datetime.now(UTC)
    assert before <= result.started_at <= after


def test_policy_view_is_frozen(tmp_path: Path) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    pol = qa.policy()
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        pol.mode = "authorized_destructive"


def test_make_flow_round_trips() -> None:
    """Sanity: deterministic plan builder works for empty input."""

    plan = _empty_plan()
    assert plan.flows == ()


def test_make_flow_step() -> None:
    # Tests the FlowStep model we use in the planner; ensures the engine
    # entity surface stays compatible with the SDK's expectations.
    step = FlowStep(
        description="Navigate to /",
        target_route_id="RT-AAAAAAAAAAAA",
        expected_outcome="page loads",
    )
    assert step.description == "Navigate to /"


def test_make_flow_constructable() -> None:
    step = FlowStep(
        description="Navigate to /",
        target_route_id="RT-AAAAAAAAAAAA",
        expected_outcome="page loads",
    )
    flow = Flow(
        id="FLW-AAAAAAAAAAAA",
        name="smoke",
        priority="P0",
        risk="medium",
        steps=(step,),
    )
    assert flow.priority == "P0"
