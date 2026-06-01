// — wire types for the per-route performance JSON artifacts.
// These mirror the Pydantic models in modules/performance/models.py
// exactly. Bump PERF_RESULT_SCHEMA_VERSION on both sides together.

export const PERF_RESULT_SCHEMA_VERSION = '1';

export interface PageMetricSample {
  readonly lcp_ms: number | null;
  readonly cls: number | null;
  readonly inp_ms: number | null;
  readonly ttfb_ms: number | null;
  readonly dcl_ms: number | null;
  readonly load_ms: number | null;
}

export interface PageMetricsSummary {
  readonly samples: readonly PageMetricSample[];
  readonly median_lcp_ms: number | null;
  readonly median_cls: number | null;
  readonly median_inp_ms: number | null;
  readonly median_ttfb_ms: number | null;
  readonly median_dcl_ms: number | null;
  readonly median_load_ms: number | null;
  readonly inp_supported: boolean;
}

export interface ApiSample {
  readonly endpoint: string;
  readonly method: string;
  readonly duration_ms: number;
  readonly status: number;
}

export interface ApiEndpointSummary {
  readonly endpoint: string;
  readonly method: string;
  readonly count: number;
  readonly p50_ms: number;
  readonly p95_ms: number;
  readonly max_ms: number;
}

export interface BundleSummary {
  readonly transfer_total_kb: number;
  readonly decoded_total_kb: number;
  readonly file_count: number;
}

export interface LongTaskSummary {
  readonly count: number;
  readonly total_blocking_ms: number;
  readonly longest_ms: number;
}

export interface NavStabilitySample {
  readonly js_heap_bytes: number | null;
  readonly dom_node_count: number | null;
}

export interface NavStabilitySummary {
  readonly samples: readonly NavStabilitySample[];
  readonly dom_growth_pct: number | null;
  readonly memory_growth_pct: number | null;
  readonly memory_supported: boolean;
}

export interface PerformancePageResult {
  readonly route: string;
  readonly url: string;
  readonly fetched_at: string;
  readonly page_metrics: PageMetricsSummary;
  readonly api_endpoints: readonly ApiEndpointSummary[];
  readonly api_samples: readonly ApiSample[];
  readonly bundle: BundleSummary;
  readonly long_tasks: LongTaskSummary;
  readonly nav_stability: NavStabilitySummary;
  readonly duration_ms: number;
  readonly schema_version: string;
  readonly error: string | null;
}

export interface PerformanceRunOutcome {
  readonly pages: readonly PerformancePageResult[];
  readonly incomplete: boolean;
}
