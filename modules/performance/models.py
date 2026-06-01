"""Typed performance result models (, ADR-0017, CLAUDE §27).

The performance module follows the same shape as the accessibility
module: per-route synthetic measurements, a dedicated runner Protocol,
typed Pydantic wire models, and Findings produced from the deterministic
budget evaluators. There is no :class:`engine.runner.results.TestExecution`
analogue — checks are per-route, not per-spec.

All numeric fields are bounded so a misbehaving TS runner cannot persist
absurd values without triggering a validation error.

Schema versions are locked under ADR-0017 §5. Bump the constant when the
wire shape changes.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

PERF_RESULT_SCHEMA_VERSION = "1"
"""Wire format of the ``perf/<route-slug>.json`` envelope."""


class PageMetricSample(BaseModel):
    """One observation of the page-level synthetic metrics for a route.

    Values are in milliseconds for time-based metrics; CLS is unitless.
    Optional fields may be ``None`` when the browser did not surface the
    metric (e.g. INP requires interaction, which the synthetic load
    cannot always trigger).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lcp_ms: float | None = Field(default=None, ge=0.0, le=120_000.0)
    cls: float | None = Field(default=None, ge=0.0, le=10.0)
    inp_ms: float | None = Field(default=None, ge=0.0, le=120_000.0)
    ttfb_ms: float | None = Field(default=None, ge=0.0, le=120_000.0)
    dcl_ms: float | None = Field(default=None, ge=0.0, le=120_000.0)
    load_ms: float | None = Field(default=None, ge=0.0, le=120_000.0)


class PageMetricsSummary(BaseModel):
    """Median over N :class:`PageMetricSample` records for one route."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    samples: tuple[PageMetricSample, ...] = Field(default_factory=tuple, max_length=20)
    median_lcp_ms: float | None = Field(default=None, ge=0.0)
    median_cls: float | None = Field(default=None, ge=0.0)
    median_inp_ms: float | None = Field(default=None, ge=0.0)
    median_ttfb_ms: float | None = Field(default=None, ge=0.0)
    median_dcl_ms: float | None = Field(default=None, ge=0.0)
    median_load_ms: float | None = Field(default=None, ge=0.0)
    inp_supported: bool = False


class ApiSample(BaseModel):
    """One observed API call duration during a synthetic page load."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    endpoint: str = Field(min_length=1, max_length=512)
    method: str = Field(min_length=1, max_length=16)
    duration_ms: float = Field(ge=0.0, le=600_000.0)
    status: int = Field(ge=0, le=999)


class ApiEndpointSummary(BaseModel):
    """Per-endpoint summary of API call durations across all samples."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    endpoint: str = Field(min_length=1, max_length=512)
    method: str = Field(min_length=1, max_length=16)
    count: int = Field(ge=0)
    p50_ms: float = Field(ge=0.0)
    p95_ms: float = Field(ge=0.0)
    max_ms: float = Field(ge=0.0)


class BundleSummary(BaseModel):
    """JavaScript bundle transfer + decoded size totals for a route."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transfer_total_kb: float = Field(ge=0.0)
    decoded_total_kb: float = Field(ge=0.0)
    file_count: int = Field(ge=0)


class LongTaskSummary(BaseModel):
    """Aggregate long-task profile observed during page load."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = Field(ge=0)
    total_blocking_ms: float = Field(ge=0.0)
    longest_ms: float = Field(ge=0.0)


class NavStabilitySample(BaseModel):
    """One repeated-nav observation (JS heap + DOM node count)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    js_heap_bytes: float | None = Field(default=None, ge=0.0)
    dom_node_count: int | None = Field(default=None, ge=0)


class NavStabilitySummary(BaseModel):
    """Memory + DOM growth summary across N repeated visits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    samples: tuple[NavStabilitySample, ...] = Field(default_factory=tuple, max_length=50)
    dom_growth_pct: float | None = Field(default=None, ge=-100.0, le=100_000.0)
    memory_growth_pct: float | None = Field(default=None, ge=-100.0, le=100_000.0)
    memory_supported: bool = False


class PerformancePageResult(BaseModel):
    """Aggregate performance result for one route (CLAUDE §27: synthetic).

    Every numeric the Python layer reads comes from this envelope; the
    Python deterministic evaluators are the single source of truth for
    budget violations.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = PERF_RESULT_SCHEMA_VERSION

    route: str = Field(min_length=1, max_length=2048)
    url: str = Field(min_length=1, max_length=2048)
    fetched_at: str = Field(min_length=1, max_length=64)
    page_metrics: PageMetricsSummary = Field(default_factory=PageMetricsSummary)
    api_endpoints: tuple[ApiEndpointSummary, ...] = Field(default_factory=tuple, max_length=500)
    api_samples: tuple[ApiSample, ...] = Field(default_factory=tuple, max_length=5000)
    bundle: BundleSummary = Field(
        default_factory=lambda: BundleSummary(
            transfer_total_kb=0.0,
            decoded_total_kb=0.0,
            file_count=0,
        )
    )
    long_tasks: LongTaskSummary = Field(
        default_factory=lambda: LongTaskSummary(
            count=0,
            total_blocking_ms=0.0,
            longest_ms=0.0,
        )
    )
    nav_stability: NavStabilitySummary = Field(default_factory=NavStabilitySummary)
    duration_ms: int = Field(ge=0)
    schema_version: str = Field(default=PERF_RESULT_SCHEMA_VERSION)
    error: str | None = Field(default=None, max_length=2_000)


class PerformanceRunOutcome(BaseModel):
    """Aggregate output of running the performance module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pages: tuple[PerformancePageResult, ...] = Field(default_factory=tuple, max_length=500)
    incomplete: bool = False
    duration_ms: int = Field(ge=0)

    @property
    def total_pages(self) -> int:
        return len(self.pages)


__all__ = [
    "ApiEndpointSummary",
    "ApiSample",
    "BundleSummary",
    "LongTaskSummary",
    "NavStabilitySample",
    "NavStabilitySummary",
    "PERF_RESULT_SCHEMA_VERSION",
    "PageMetricSample",
    "PageMetricsSummary",
    "PerformancePageResult",
    "PerformanceRunOutcome",
]
