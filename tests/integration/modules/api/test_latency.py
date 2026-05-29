"""Phase 22.06 — API latency dedup check.

The API module defers latency-budget enforcement to the Phase 12 perf
module to avoid duplicate findings (one of the two phase-22 task
requirements is "no duplicate findings across modules"). Phase 22's
contribution is therefore an explicit, evidence-bearing skip that
references the perf-module finding category.
"""

from __future__ import annotations

import pytest
from engine.config.schema import ApiConfig, RootConfig

from modules.api.checks.latency import run_latency_check


@pytest.fixture
def api_config() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(),
    )


def test_latency_check_skips_and_references_perf_module(
    api_config: RootConfig,
) -> None:
    result = run_latency_check(results=(), config=api_config)
    assert result.check == "latency"
    assert result.skipped is True
    assert result.issues == ()
    assert result.skip_reason is not None
    # The skip reason must name the perf-module category so operators can
    # trace where the budget is actually enforced.
    assert "perf/api_latency" in result.skip_reason
    assert f"{api_config.performance.budgets.api_p95_ms}ms" in result.skip_reason
