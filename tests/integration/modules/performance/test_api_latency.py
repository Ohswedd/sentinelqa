"""Integration test for API P95 latency budget."""

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
    ApiEndpointSummary,
    BundleSummary,
    LongTaskSummary,
    NavStabilitySummary,
    PageMetricSample,
    PageMetricsSummary,
    PerformancePageResult,
)
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


def _page_with_endpoint(p95_ms: float, *, count: int = 10) -> PerformancePageResult:
    summary = PageMetricsSummary(
        samples=(PageMetricSample(lcp_ms=1500.0, cls=0.02, ttfb_ms=80.0),),
        median_lcp_ms=1500.0,
        median_cls=0.02,
        median_ttfb_ms=80.0,
        inp_supported=False,
    )
    endpoint = ApiEndpointSummary(
        endpoint="/api/users/[id]",
        method="GET",
        count=count,
        p50_ms=p95_ms / 2,
        p95_ms=p95_ms,
        max_ms=p95_ms * 1.2,
    )
    return PerformancePageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        page_metrics=summary,
        api_endpoints=(endpoint,),
        bundle=BundleSummary(transfer_total_kb=200.0, decoded_total_kb=400.0, file_count=2),
        long_tasks=LongTaskSummary(count=0, total_blocking_ms=0.0, longest_ms=0.0),
        nav_stability=NavStabilitySummary(),
        duration_ms=42,
    )


def test_slow_endpoint_emits_synthetic_finding(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page_with_endpoint(p95_ms=1200.0),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    findings_by_cat = {f.category for f in result.findings}
    assert "perf.api.p95" in findings_by_cat
    api_finding = next(f for f in result.findings if f.category == "perf.api.p95")
    assert "GET" in api_finding.title
    assert "/api/users/[id]" in api_finding.title
    assert "Synthetic performance check" in api_finding.description


def test_fast_endpoint_emits_no_finding(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page_with_endpoint(p95_ms=200.0),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert all(f.category != "perf.api.p95" for f in result.findings)


def test_below_min_samples_endpoint_is_skipped(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page_with_endpoint(p95_ms=2000.0, count=3),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert all(f.category != "perf.api.p95" for f in result.findings)
