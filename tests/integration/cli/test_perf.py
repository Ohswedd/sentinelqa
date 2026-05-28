"""CLI integration tests for ``sentinel perf`` (Phase 12.06)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from modules.performance.models import (
    BundleSummary,
    LongTaskSummary,
    NavStabilitySummary,
    PageMetricSample,
    PageMetricsSummary,
    PerformancePageResult,
    PerformanceRunOutcome,
)
from modules.performance.runner import (
    PerformanceInvocation,
    PerformanceRunnerError,
)
from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


def _page(*, route: str = "/", lcp_ms: float = 1500.0) -> PerformancePageResult:
    summary = PageMetricsSummary(
        samples=(PageMetricSample(lcp_ms=lcp_ms, cls=0.02, ttfb_ms=80.0),),
        median_lcp_ms=lcp_ms,
        median_cls=0.02,
        median_ttfb_ms=80.0,
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


class _StubPerfRunner:
    def __init__(
        self,
        outcome: PerformanceRunOutcome,
        *,
        raise_with: Exception | None = None,
    ) -> None:
        self._outcome = outcome
        self._raise_with = raise_with
        self.invocation: PerformanceInvocation | None = None

    def run(self, invocation: PerformanceInvocation) -> PerformanceRunOutcome:
        self.invocation = invocation
        if self._raise_with is not None:
            raise self._raise_with
        return self._outcome


def _patch_runner(
    monkeypatch: pytest.MonkeyPatch,
    outcome: PerformanceRunOutcome,
    *,
    raise_with: Exception | None = None,
) -> _StubPerfRunner:
    stub = _StubPerfRunner(outcome, raise_with=raise_with)
    from modules.performance.module import PerformanceModule

    def _stub_factory(cfg: Any, sd: Any) -> Any:
        return PerformanceModule(cfg, sd, runner_factory=lambda _c, _s: stub)

    monkeypatch.setattr("modules.performance.module._factory", _stub_factory)
    monkeypatch.setitem(
        __import__("engine.orchestrator.registry", fromlist=["default_registry"])
        .default_registry()
        .modules,
        "performance",
        _stub_factory,
    )
    return stub


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_perf_compliant_page_exits_zero(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    stub = _patch_runner(monkeypatch, PerformanceRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "module_status     : passed" in result.stdout
    assert "synthetic (lab; not Real-User Monitoring)" in result.stdout
    assert stub.invocation is not None
    assert stub.invocation.routes == ("/",)


def test_perf_routes_flag_passes_subset(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    stub = _patch_runner(
        monkeypatch,
        PerformanceRunOutcome(pages=(_page(), _page(route="/dashboard")), duration_ms=10),
    )

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf", "--routes", "/,/dashboard"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert stub.invocation is not None
    assert stub.invocation.routes == ("/", "/dashboard")


def test_perf_samples_flag_overrides_default(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    stub = _patch_runner(monkeypatch, PerformanceRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf", "--samples", "7"])
    assert result.exit_code == 0
    assert stub.invocation is not None
    assert stub.invocation.samples == 7


def test_perf_repeated_nav_flag_overrides_default(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    stub = _patch_runner(monkeypatch, PerformanceRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf", "--repeated-nav-samples", "9"])
    assert result.exit_code == 0
    assert stub.invocation is not None
    assert stub.invocation.repeated_nav_samples == 9


def test_perf_json_mode_emits_synthetic_label(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(monkeypatch, PerformanceRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["--json", "perf"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["command"] == "perf"
    assert payload["module_status"] == "passed"
    assert payload["measurement_kind"] == "synthetic"


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_perf_high_finding_blocks_with_exit_one(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    page = _page(lcp_ms=6000.0)  # 140% overage → high severity.
    _patch_runner(monkeypatch, PerformanceRunOutcome(pages=(page,), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf"])
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "high_or_critical  : 1" in result.stdout


def test_perf_sentinel_ts_missing_exits_five(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(
        monkeypatch,
        PerformanceRunOutcome(pages=(), duration_ms=0),
        raise_with=PerformanceRunnerError("sentinel-ts binary not found."),
    )

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf"])
    assert result.exit_code == 5, result.stdout + result.stderr


def test_perf_runner_error_exits_six(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(
        monkeypatch,
        PerformanceRunOutcome(pages=(), duration_ms=0),
        raise_with=PerformanceRunnerError("Chromium crashed"),
    )

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf"])
    assert result.exit_code == 6, result.stdout + result.stderr


def test_perf_incomplete_run_blocks_with_exit_one(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(
        monkeypatch,
        PerformanceRunOutcome(pages=(_page(),), incomplete=True, duration_ms=10),
    )

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf"])
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "module_status     : incomplete" in result.stdout


def test_perf_invalid_routes_flag_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf", "--routes", " , , "])
    assert result.exit_code == 2, result.stdout + result.stderr


def test_perf_invalid_samples_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf", "--samples", "0"])
    assert result.exit_code == 2


def test_perf_invalid_repeated_nav_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf", "--repeated-nav-samples", "1"])
    assert result.exit_code == 2


def test_perf_missing_config_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)

    cli = build_app()
    result = cli_runner.invoke(cli, ["perf"])
    assert result.exit_code == 2
