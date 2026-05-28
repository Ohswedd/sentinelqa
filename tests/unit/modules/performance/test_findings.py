"""Unit tests for :mod:`modules.performance.findings` (Phase 12.04+)."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.config.schema import PerformanceBudgets
from engine.domain.ids import IdGenerator

from modules.performance.findings import findings_from_page, findings_from_pages, short_hash
from modules.performance.models import (
    ApiEndpointSummary,
    BundleSummary,
    LongTaskSummary,
    NavStabilitySample,
    NavStabilitySummary,
    PageMetricSample,
    PageMetricsSummary,
    PerformancePageResult,
)
from modules.performance.nav_stability import summarise_nav_samples


def _id_gen() -> IdGenerator:
    return IdGenerator()


def _ts() -> datetime:
    return datetime(2026, 5, 28, 0, 0, 0, tzinfo=UTC)


def _page(
    route: str = "/",
    *,
    page_metrics: PageMetricsSummary | None = None,
    api_endpoints: tuple[ApiEndpointSummary, ...] = (),
    bundle: BundleSummary | None = None,
    long_tasks: LongTaskSummary | None = None,
    nav_stability: NavStabilitySummary | None = None,
) -> PerformancePageResult:
    return PerformancePageResult(
        route=route,
        url=f"http://localhost:3000{route}",
        fetched_at="2026-05-28T00:00:00+00:00",
        page_metrics=page_metrics or PageMetricsSummary(),
        api_endpoints=api_endpoints,
        bundle=bundle or BundleSummary(transfer_total_kb=0.0, decoded_total_kb=0.0, file_count=0),
        long_tasks=long_tasks or LongTaskSummary(count=0, total_blocking_ms=0.0, longest_ms=0.0),
        nav_stability=nav_stability or NavStabilitySummary(),
        duration_ms=42,
    )


def test_compliant_page_produces_no_findings() -> None:
    findings = findings_from_page(
        page=_page(
            page_metrics=PageMetricsSummary(
                samples=(PageMetricSample(lcp_ms=1500.0, cls=0.02, ttfb_ms=80.0),),
                median_lcp_ms=1500.0,
                median_cls=0.02,
                median_ttfb_ms=80.0,
            ),
            bundle=BundleSummary(transfer_total_kb=200.0, decoded_total_kb=400.0, file_count=3),
            long_tasks=LongTaskSummary(count=0, total_blocking_ms=0.0, longest_ms=0.0),
        ),
        budgets=PerformanceBudgets(),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=_id_gen(),
        now=_ts(),
    )
    assert findings == ()


def test_lcp_violation_labels_synthetic_and_uses_high_severity_when_overage_50_plus() -> None:
    findings = findings_from_page(
        page=_page(
            page_metrics=PageMetricsSummary(
                samples=(PageMetricSample(lcp_ms=4000.0),),
                median_lcp_ms=4000.0,
            ),
        ),
        budgets=PerformanceBudgets(),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=_id_gen(),
        now=_ts(),
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.category == "perf.page.lcp_ms"
    assert "Synthetic performance check" in f.title
    assert "Synthetic performance check" in f.description
    # 4000ms vs budget 2500ms → 60% overage → high.
    assert f.severity == "high"
    assert f.confidence == 0.9
    assert f.evidence[0].type == "console_log"  # no artifact_path → log fallback.


def test_api_p95_violation_uses_high_severity_when_overage_100_plus() -> None:
    summary = ApiEndpointSummary(
        endpoint="/api/users/[id]",
        method="GET",
        count=10,
        p50_ms=600.0,
        p95_ms=1200.0,
        max_ms=1500.0,
    )
    findings = findings_from_page(
        page=_page(api_endpoints=(summary,)),
        budgets=PerformanceBudgets(),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=_id_gen(),
        now=_ts(),
        api_min_samples=5,
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.category == "perf.api.p95"
    # 1200 vs 500 → 140% overage → high.
    assert f.severity == "high"
    assert "Synthetic performance check" in f.description


def test_bundle_size_violation_emitted_with_synthetic_label() -> None:
    findings = findings_from_page(
        page=_page(
            bundle=BundleSummary(transfer_total_kb=900.0, decoded_total_kb=1800.0, file_count=7),
        ),
        budgets=PerformanceBudgets(),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=_id_gen(),
        now=_ts(),
    )
    assert any(f.category == "perf.bundle.size" for f in findings)
    bundle_finding = next(f for f in findings if f.category == "perf.bundle.size")
    assert "Synthetic performance check" in bundle_finding.description


def test_long_task_violation_emitted_with_synthetic_label() -> None:
    findings = findings_from_page(
        page=_page(
            long_tasks=LongTaskSummary(count=4, total_blocking_ms=600.0, longest_ms=200.0),
        ),
        budgets=PerformanceBudgets(),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=_id_gen(),
        now=_ts(),
    )
    long_task_finding = next(f for f in findings if f.category == "perf.cpu.long_tasks")
    assert long_task_finding.severity == "high"
    assert "Synthetic performance check" in long_task_finding.description


def test_nav_stability_violation_is_low_confidence_and_labels_potential() -> None:
    nav = summarise_nav_samples(
        [
            NavStabilitySample(js_heap_bytes=1000.0, dom_node_count=100),
            NavStabilitySample(js_heap_bytes=1500.0, dom_node_count=200),
        ]
    )
    findings = findings_from_page(
        page=_page(nav_stability=nav),
        budgets=PerformanceBudgets(),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=_id_gen(),
        now=_ts(),
    )
    assert all(f.severity == "low" for f in findings)
    assert all(f.confidence == 0.5 for f in findings)
    assert all("potential memory leak" in f.title for f in findings)


def test_findings_from_pages_aggregates_routes() -> None:
    pages = (
        _page(
            route="/",
            page_metrics=PageMetricsSummary(median_lcp_ms=4000.0),
        ),
        _page(
            route="/dashboard",
            page_metrics=PageMetricsSummary(median_lcp_ms=4000.0),
        ),
    )
    findings = findings_from_pages(
        pages=pages,
        budgets=PerformanceBudgets(),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=_id_gen(),
        artifact_paths={
            "/": "perf/root.json",
            "/dashboard": "perf/-dashboard.json",
        },
        now=_ts(),
    )
    routes = {f.location.route for f in findings}
    assert routes == {"/", "/dashboard"}
    # Evidence resolves to the per-route artifact path when supplied.
    assert any("perf/root.json" in str(e.path) for f in findings for e in f.evidence)


def test_short_hash_stable() -> None:
    assert short_hash("a", "b") == short_hash("a", "b")
    assert short_hash("a", "b") != short_hash("a", "c")
