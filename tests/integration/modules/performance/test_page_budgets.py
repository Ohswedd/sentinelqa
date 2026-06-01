"""Integration test for page-budget evaluation.

The TS subcommand (``sentinel-ts audit-perf``) writes the median
LCP/CLS/INP/TTFB/load/DCL per route. This test verifies that:

- A compliant fixture → zero findings, module ``passed``.
- A deliberately slow fixture (LCP 6000ms) → one ``perf.page.lcp_ms``
 finding with high severity, module ``failed``, **synthetic** label
 present in the description.

We feed the module a :class:`StubPerformanceRunner` with the per-route
shape the TS side would have written.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from engine.config.loader import load_config
from engine.config.schema import RootConfig
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
    PageMetricSample,
    PageMetricsSummary,
    PerformancePageResult,
)
from modules.performance.runner import StubPerformanceRunner


def _config(tmp_path: Path) -> RootConfig:
    cfg = tmp_path / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: x\ntarget:\n  base_url: http://localhost:3000\n"
        "  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    return load_config(cfg)


def _ctx(tmp_path: Path, *, options: dict[str, object] | None = None) -> ModuleContext:
    config = _config(tmp_path)
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
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
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def _empty_page(route: str, *, lcp_ms: float | None) -> PerformancePageResult:
    summary = PageMetricsSummary(
        samples=(
            PageMetricSample(
                lcp_ms=lcp_ms,
                cls=0.02,
                ttfb_ms=80.0,
                dcl_ms=200.0,
                load_ms=500.0,
            ),
        ),
        median_lcp_ms=lcp_ms,
        median_cls=0.02,
        median_ttfb_ms=80.0,
        median_dcl_ms=200.0,
        median_load_ms=500.0,
        inp_supported=False,
    )
    return PerformancePageResult(
        route=route,
        url=f"http://localhost:3000{route}",
        fetched_at="2026-05-28T00:00:00+00:00",
        page_metrics=summary,
        bundle=BundleSummary(transfer_total_kb=200.0, decoded_total_kb=400.0, file_count=2),
        long_tasks=LongTaskSummary(count=0, total_blocking_ms=0.0, longest_ms=0.0),
        nav_stability=NavStabilitySummary(),
        duration_ms=42,
    )


def test_compliant_fixture_produces_no_findings(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_empty_page("/", lcp_ms=1500.0),))
    ctx = _ctx(tmp_path, options={"performance": {"routes": ("/",)}})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "passed"
    assert result.findings == ()


def test_slow_page_emits_high_severity_synthetic_finding(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_empty_page("/", lcp_ms=6000.0),))
    ctx = _ctx(tmp_path, options={"performance": {"routes": ("/",)}})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "failed"
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.category == "perf.page.lcp_ms"
    assert f.severity == "high"  # 140% overage > 50% threshold
    # CLAUDE §27 — synthetic labelling required.
    assert "Synthetic performance check" in f.description
    assert "Real-User Monitoring" in f.description
