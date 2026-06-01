"""Integration test for repeated-navigation stability."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision

from modules.performance import PerformanceModule
from modules.performance.models import (
    BundleSummary,
    LongTaskSummary,
    NavStabilitySample,
    NavStabilitySummary,
    PageMetricsSummary,
    PerformancePageResult,
)
from modules.performance.nav_stability import summarise_nav_samples
from modules.performance.runner import StubPerformanceRunner


def _ctx(tmp_path: Path) -> ModuleContext:
    cfg = tmp_path / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: x\ntarget:\n  base_url: http://localhost:3000\n"
        "  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    config = load_config(cfg)
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="performance",
        config=config,
        safety_decision=safety,
        artifacts=ArtifactDirectory(run_dir),
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options={"performance": {"routes": ("/",)}},
    )


def _page(*, nav: NavStabilitySummary) -> PerformancePageResult:
    return PerformancePageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        page_metrics=PageMetricsSummary(),
        bundle=BundleSummary(transfer_total_kb=200.0, decoded_total_kb=400.0, file_count=2),
        long_tasks=LongTaskSummary(count=0, total_blocking_ms=0.0, longest_ms=0.0),
        nav_stability=nav,
        duration_ms=42,
    )


def test_stable_fixture_emits_no_nav_finding(tmp_path: Path) -> None:
    nav = summarise_nav_samples(
        [
            NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
            NavStabilitySample(js_heap_bytes=1010.0, dom_node_count=101),
            NavStabilitySample(js_heap_bytes=1020.0, dom_node_count=102),
        ]
    )
    runner = StubPerformanceRunner(pages=(_page(nav=nav),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    nav_cats = {f.category for f in result.findings if f.category.startswith("perf.nav.")}
    assert nav_cats == set()


def test_leaky_fixture_emits_low_confidence_finding(tmp_path: Path) -> None:
    nav = summarise_nav_samples(
        [
            NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
            NavStabilitySample(js_heap_bytes=1200.0, dom_node_count=130),
            NavStabilitySample(js_heap_bytes=1500.0, dom_node_count=170),
        ]
    )
    runner = StubPerformanceRunner(pages=(_page(nav=nav),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    nav_findings = [f for f in result.findings if f.category.startswith("perf.nav.")]
    assert len(nav_findings) >= 1
    # the engineering guidelines— heuristic with low severity + low confidence.
    assert all(f.severity == "low" for f in nav_findings)
    assert all(f.confidence == 0.5 for f in nav_findings)
    assert all("potential memory leak" in f.title for f in nav_findings)
    assert all("Synthetic performance check" in f.description for f in nav_findings)
