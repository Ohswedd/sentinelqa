"""Integration test for bundle size + CPU blocking findings (Phase 12.04)."""

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
    NavStabilitySummary,
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


def _page(*, bundle_kb: float, long_task_ms: float) -> PerformancePageResult:
    return PerformancePageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        page_metrics=PageMetricsSummary(),
        bundle=BundleSummary(
            transfer_total_kb=bundle_kb,
            decoded_total_kb=bundle_kb * 2,
            file_count=3 if bundle_kb > 0 else 0,
        ),
        long_tasks=LongTaskSummary(
            count=1 if long_task_ms > 0 else 0,
            total_blocking_ms=long_task_ms,
            longest_ms=long_task_ms,
        ),
        nav_stability=NavStabilitySummary(),
        duration_ms=42,
    )


def test_large_bundle_emits_bundle_size_finding(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page(bundle_kb=900.0, long_task_ms=0.0),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    finding = next(f for f in result.findings if f.category == "perf.bundle.size")
    assert finding.severity == "high"
    assert "Synthetic performance check" in finding.description


def test_blocked_main_thread_emits_long_task_finding(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page(bundle_kb=100.0, long_task_ms=500.0),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    finding = next(f for f in result.findings if f.category == "perf.cpu.long_tasks")
    assert finding.severity == "high"
    assert "Synthetic performance check" in finding.description


def test_compliant_bundle_and_cpu_emits_nothing(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page(bundle_kb=300.0, long_task_ms=80.0),))
    ctx = _ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    cats = {f.category for f in result.findings}
    assert "perf.bundle.size" not in cats
    assert "perf.cpu.long_tasks" not in cats
