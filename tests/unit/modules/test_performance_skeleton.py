"""Unit tests for :mod:`modules.performance`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import ModuleRegistry
from engine.policy.safety import SafetyDecision

from modules.performance import (
    PerformanceModule,
    PerformanceModuleOptions,
    register_with_default_registry,
)
from modules.performance.models import (
    ApiEndpointSummary,
    BundleSummary,
    LongTaskSummary,
    NavStabilitySummary,
    PageMetricSample,
    PageMetricsSummary,
    PerformancePageResult,
)
from modules.performance.module import _factory
from modules.performance.runner import (
    PerformanceInvocation,
    PerformanceRunnerError,
    StubPerformanceRunner,
)


def _write_config(
    root: Path,
    *,
    base_url: str = "http://localhost:3000",
    performance_block: str = "",
) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        f"target:\n  base_url: {base_url}\n  allowed_hosts: [localhost, 127.0.0.1]\n"
        + performance_block,
        encoding="utf-8",
    )
    return p


def _build_ctx(
    tmp_path: Path,
    *,
    base_url: str = "http://localhost:3000",
    options: Mapping[str, Any] | None = None,
    performance_block: str = "",
) -> ModuleContext:
    config_path = _write_config(tmp_path, base_url=base_url, performance_block=performance_block)
    config = load_config(config_path)
    artifacts_root = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(artifacts_root)
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
        run_dir=artifacts_root,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def _page(
    route: str = "/",
    *,
    page_metrics: PageMetricsSummary | None = None,
    api_endpoints: tuple[ApiEndpointSummary, ...] = (),
    bundle_kb: float = 0.0,
    long_task_ms: float = 0.0,
    nav_stability: NavStabilitySummary | None = None,
) -> PerformancePageResult:
    return PerformancePageResult(
        route=route,
        url=f"http://localhost:3000{route}",
        fetched_at="2026-05-28T00:00:00+00:00",
        page_metrics=page_metrics
        or PageMetricsSummary(
            samples=(
                PageMetricSample(
                    lcp_ms=1500.0, cls=0.02, ttfb_ms=100.0, dcl_ms=400.0, load_ms=900.0
                ),
            ),
            median_lcp_ms=1500.0,
            median_cls=0.02,
            median_ttfb_ms=100.0,
            median_dcl_ms=400.0,
            median_load_ms=900.0,
            inp_supported=False,
        ),
        api_endpoints=api_endpoints,
        bundle=BundleSummary(
            transfer_total_kb=bundle_kb,
            decoded_total_kb=bundle_kb * 2,
            file_count=2 if bundle_kb > 0 else 0,
        ),
        long_tasks=LongTaskSummary(
            count=1 if long_task_ms > 0 else 0,
            total_blocking_ms=long_task_ms,
            longest_ms=long_task_ms,
        ),
        nav_stability=nav_stability or NavStabilitySummary(),
        duration_ms=42,
    )


# ---------------------------------------------------------------------------
# Module class basics
# ---------------------------------------------------------------------------


def test_performance_module_is_sentinel_module(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = PerformanceModule(ctx.config, ctx.safety_decision)
    assert isinstance(module, SentinelModule)
    assert PerformanceModule.name == "performance"


def test_factory_returns_performance_module_instance(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    instance = _factory(ctx.config, ctx.safety_decision)
    assert isinstance(instance, PerformanceModule)


def test_validate_prerequisites_is_noop(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = PerformanceModule(ctx.config, ctx.safety_decision)
    module.validate_prerequisites(ctx)  # no exception


def test_plan_returns_empty_routes_are_resolved_in_execute(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = PerformanceModule(ctx.config, ctx.safety_decision)
    assert module.plan(ctx) == ()


# ---------------------------------------------------------------------------
# Run orchestration (stub runner)
# ---------------------------------------------------------------------------


def test_run_with_no_routes_skips(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=())
    ctx = _build_ctx(tmp_path)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    # No CLI/discovery/config-driven routes → the module short-circuits
    # without spawning the runner.
    assert runner.invocation is None
    assert result.status == "skipped"


def test_run_with_compliant_page_passes(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page(),))
    ctx = _build_ctx(tmp_path, options={"performance": {"routes": ("/",)}})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "passed"
    assert result.findings == ()
    assert result.metrics["pages"] == 1


def test_run_with_lcp_violation_emits_finding(tmp_path: Path) -> None:
    page = _page(
        page_metrics=PageMetricsSummary(
            samples=(PageMetricSample(lcp_ms=8000.0),),
            median_lcp_ms=8000.0,
            median_cls=0.0,
            median_ttfb_ms=100.0,
            median_dcl_ms=400.0,
            median_load_ms=900.0,
            inp_supported=False,
        ),
    )
    runner = StubPerformanceRunner(pages=(page,))
    ctx = _build_ctx(tmp_path, options={"performance": {"routes": ("/",)}})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "failed"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.module == "performance"
    assert finding.category == "perf.page.lcp_ms"
    assert finding.severity == "high"
    assert "Synthetic performance check" in finding.description
    # Synthetic-labelling guard: must NOT claim real-user data.
    assert "Real-User Monitoring" in finding.description


def test_incomplete_run_translates_to_incomplete_status(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page(),), incomplete=True)
    ctx = _build_ctx(tmp_path, options={"performance": {"routes": ("/",)}})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "incomplete"


def test_runner_error_bubbles_up_for_orchestrator(tmp_path: Path) -> None:
    class _Boom:
        def run(self, _: PerformanceInvocation) -> Any:
            raise PerformanceRunnerError("sentinel-ts missing")

    ctx = _build_ctx(tmp_path, options={"performance": {"routes": ("/",)}})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: _Boom()
    )
    with pytest.raises(PerformanceRunnerError):
        module.run(ctx)


# ---------------------------------------------------------------------------
# Options resolution
# ---------------------------------------------------------------------------


def test_options_dict_routes_string_normalised(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page("/dashboard"),))
    ctx = _build_ctx(
        tmp_path,
        options={"performance": {"routes": "/dashboard"}},
    )
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/dashboard",)


def test_options_dict_routes_list_with_normalization(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=())
    ctx = _build_ctx(
        tmp_path,
        options={"performance": {"routes": ["/", "/dashboard", "settings"]}},
    )
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/", "/dashboard", "/settings")


def test_options_typed_dataclass_round_trip(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page("/profile"),))
    opts = PerformanceModuleOptions(routes=("/profile",), samples=7, repeated_nav_samples=3)
    ctx = _build_ctx(tmp_path, options={"performance": opts})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/profile",)
    assert runner.invocation.samples == 7
    assert runner.invocation.repeated_nav_samples == 3


def test_options_dict_discovery_path_drives_routes(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=())
    discovery = tmp_path / "discovery.json"
    discovery.write_text(
        '{"routes": [{"path": "/"}, {"path": "/dashboard"}, "/settings", "/"]}',
        encoding="utf-8",
    )
    ctx = _build_ctx(
        tmp_path,
        options={"performance": {"discovery_path": str(discovery)}},
    )
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/", "/dashboard", "/settings")


def test_options_dict_discovery_path_missing_falls_back_to_skip(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=())
    ctx = _build_ctx(
        tmp_path,
        options={"performance": {"discovery_path": tmp_path / "nope.json"}},
    )
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert runner.invocation is None
    assert result.status == "skipped"


def test_config_routes_used_when_options_omit_them(tmp_path: Path) -> None:
    runner = StubPerformanceRunner(pages=(_page("/"),))
    block = "\nperformance:\n  routes:\n    - /\n    - /profile\n"
    ctx = _build_ctx(tmp_path, performance_block=block)
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/", "/profile")


def test_module_metrics_include_synthetic_aggregates(tmp_path: Path) -> None:
    api_endpoint = ApiEndpointSummary(
        endpoint="/api/users", method="GET", count=3, p50_ms=10.0, p95_ms=15.0, max_ms=20.0
    )
    page = _page(
        api_endpoints=(api_endpoint,),
        bundle_kb=250.5,
        long_task_ms=80.0,
    )
    runner = StubPerformanceRunner(pages=(page,))
    ctx = _build_ctx(tmp_path, options={"performance": {"routes": ("/",)}})
    module = PerformanceModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.metrics["pages"] == 1
    assert result.metrics["api_endpoints"] == 1
    assert result.metrics["long_tasks"] == 1
    assert result.metrics["bundle_transfer_kb_total"] == 250.5


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def test_register_with_default_registry_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)
    assert "performance" in registry.modules


def test_register_with_explicit_registry_records_factory() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    factory = registry.modules["performance"]
    assert factory is _factory
