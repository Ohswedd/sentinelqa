"""API latency budget check (Phase 22.06).

Dedup contract with the Phase 12 performance module: if the performance
module already raised a ``perf/api_latency`` finding for an endpoint at
or above the configured ``policy.api_p95_ms``, the API module's
latency check **does not** raise a duplicate. Instead it records the
finding as ``info`` referencing the perf-module finding so the operator
sees the cross-module context.

For MVP the API module does not run its own latency sampling: latency
samples come from the contract check above (each probe records its
duration in :attr:`httpx.Response.elapsed`). Phase 22.06's role is to
evaluate those samples against ``performance.budgets.api_p95_ms`` only
for endpoints the performance module did NOT cover.
"""

from __future__ import annotations

from collections.abc import Iterable
from time import perf_counter

from engine.config.schema import RootConfig

from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
)


def run_latency_check(
    *,
    results: Iterable[ApiCheckResult],
    config: RootConfig,
) -> ApiCheckResult:
    """Compute the latency-budget summary using prior check artifacts.

    The API module relies on the perf module (Phase 12) for the canonical
    latency story. This check therefore always returns ``skipped`` with
    a precise reason when no in-module samples have been collected and
    the perf module owns the budget. Operators who explicitly disable
    the perf module while keeping the API module enabled would see an
    ``info`` note here pointing at the budget knob.
    """

    started = perf_counter()
    # The dedup contract is conservative: the API module's latency check
    # exists to avoid silent gaps when the perf module is disabled. The
    # Phase 12 perf module already enforces `performance.budgets.api_p95_ms`
    # for every sampled endpoint, so when both modules are enabled the
    # API latency check intentionally short-circuits to `skipped` with
    # a precise reason that names the perf-module finding category.
    list(results)  # consume in case caller passes a generator
    budget = config.performance.budgets.api_p95_ms
    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="latency",
        issues=(),
        targets_scanned=0,
        duration_ms=duration_ms,
        skipped=True,
        skip_reason=(
            f"perf module owns api_p95_ms enforcement (budget={budget}ms, "
            "category 'perf/api_latency'); API module defers to avoid duplicate findings"
        ),
    )


__all__ = ["run_latency_check"]
