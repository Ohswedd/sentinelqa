// Phase 12 — orchestrates the per-route performance audit and writes the
// JSON artifacts (`<run-dir>/perf/<route-slug>.json` + `index.json`)
// the Python module reads.
//
// The orchestrator accepts an injectable `launcher` so the CLI subcommand
// can wire in Playwright in production while tests substitute a
// deterministic stub. CLAUDE §27: the per-route artifact carries the
// `schema_version: "1"` envelope used by both runtimes.

import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve as resolvePath } from 'node:path';

import { prepLongTaskObserver, readLongTaskEntries, summariseLongTasks } from './long_tasks.js';
import { readNavSample, normaliseNavSample } from './nav_stability.js';
import {
  ingestObservation,
  newCollectorState,
  summariseBundle,
  type NetworkObserverPage,
  type NetworkResponseHandle,
  type NetworkResponseObservation,
} from './network.js';
import { collectPageMetrics, type PageMetricsCollectorPage } from './page_metrics.js';
import {
  PERF_RESULT_SCHEMA_VERSION,
  type ApiSample,
  type NavStabilitySample,
  type PageMetricSample,
  type PageMetricsSummary,
  type PerformancePageResult,
  type PerformanceRunOutcome,
} from './types.js';

export interface AuditPerfRunConfig {
  readonly schema_version: string;
  readonly run_id: string;
  readonly target: string;
  readonly out_dir: string;
  readonly routes: readonly string[];
  readonly samples: number;
  readonly repeated_nav_samples: number;
  readonly request_timeout_ms: number;
  readonly api_path_allowlist: readonly string[];
}

export interface AuditPerfPage extends PageMetricsCollectorPage, NetworkObserverPage {
  // Combined surface — same Playwright Page subset used by audit.
}

export interface AuditPerfBrowser {
  newPage(): Promise<AuditPerfPage>;
  close(): Promise<void>;
}

export type AuditPerfLauncher = () => Promise<AuditPerfBrowser>;

export interface AuditPerfOptions {
  readonly inputPath: string;
  readonly launcher: AuditPerfLauncher;
  readonly now?: () => Date;
}

export interface AuditPerfResult {
  readonly outcome: PerformanceRunOutcome;
  readonly indexPath: string;
}

export function loadRunConfig(raw: unknown): AuditPerfRunConfig {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    throw new Error('audit-perf run-config must be a JSON object.');
  }
  const obj = raw as Record<string, unknown>;
  const requireString = (key: string): string => {
    const v = obj[key];
    if (typeof v !== 'string' || v.length === 0) {
      throw new Error(`audit-perf run-config: '${key}' must be a non-empty string.`);
    }
    return v;
  };
  const requireStringArray = (key: string): readonly string[] => {
    const v = obj[key];
    if (!Array.isArray(v)) {
      throw new Error(`audit-perf run-config: '${key}' must be a string array.`);
    }
    const arr = v.filter((x): x is string => typeof x === 'string');
    if (arr.length === 0) {
      throw new Error(`audit-perf run-config: '${key}' must contain at least one entry.`);
    }
    return arr;
  };
  const requireInt = (key: string, min = 1): number => {
    const v = obj[key];
    if (typeof v !== 'number' || !Number.isInteger(v) || v < min) {
      throw new Error(`audit-perf run-config: '${key}' must be an integer >= ${min}.`);
    }
    return v;
  };
  const optStringArray = (key: string): readonly string[] => {
    const v = obj[key];
    if (v === undefined) return [];
    if (!Array.isArray(v)) {
      throw new Error(`audit-perf run-config: '${key}' must be a string array.`);
    }
    return v.filter((x): x is string => typeof x === 'string');
  };
  return {
    schema_version: typeof obj['schema_version'] === 'string' ? obj['schema_version'] : '1',
    run_id: requireString('run_id'),
    target: requireString('target'),
    out_dir: requireString('out_dir'),
    routes: requireStringArray('routes'),
    samples: requireInt('samples'),
    repeated_nav_samples: requireInt('repeated_nav_samples', 2),
    request_timeout_ms: requireInt('request_timeout_ms'),
    api_path_allowlist: optStringArray('api_path_allowlist'),
  };
}

export function routeSlug(route: string): string {
  if (route === '' || route === '/') return 'root';
  const cleaned = route.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  return cleaned.length === 0 ? 'root' : cleaned;
}

export function urlFor(target: string, route: string): string {
  if (route.startsWith('http://') || route.startsWith('https://')) return route;
  const stripped = target.endsWith('/') ? target.slice(0, -1) : target;
  const path = route.startsWith('/') ? route : '/' + route;
  return stripped + path;
}

// ---------------------------------------------------------------------------
// Median helpers (mirror of modules/performance/page_budget.py)
// ---------------------------------------------------------------------------

function medianOf(values: readonly number[]): number | null {
  const observed = values
    .filter((v) => typeof v === 'number' && Number.isFinite(v))
    .slice()
    .sort((a, b) => a - b);
  if (observed.length === 0) return null;
  const mid = Math.floor(observed.length / 2);
  if (observed.length % 2 === 1) {
    const v = observed[mid];
    return typeof v === 'number' ? v : null;
  }
  const lo = observed[mid - 1];
  const hi = observed[mid];
  if (typeof lo !== 'number' || typeof hi !== 'number') return null;
  return (lo + hi) / 2;
}

export function summarisePageMetrics(samples: readonly PageMetricSample[]): PageMetricsSummary {
  const inpSupported = samples.some((s) => s.inp_ms !== null);
  return {
    samples,
    median_lcp_ms: medianOf(samples.map((s) => s.lcp_ms).filter((v): v is number => v !== null)),
    median_cls: medianOf(samples.map((s) => s.cls).filter((v): v is number => v !== null)),
    median_inp_ms: medianOf(samples.map((s) => s.inp_ms).filter((v): v is number => v !== null)),
    median_ttfb_ms: medianOf(samples.map((s) => s.ttfb_ms).filter((v): v is number => v !== null)),
    median_dcl_ms: medianOf(samples.map((s) => s.dcl_ms).filter((v): v is number => v !== null)),
    median_load_ms: medianOf(samples.map((s) => s.load_ms).filter((v): v is number => v !== null)),
    inp_supported: inpSupported,
  };
}

// Per-endpoint summary mirror — keep in sync with modules.performance.api_latency.
function templateEndpoint(path: string): string {
  if (!path) return path;
  let cleaned = path.split('?')[0]?.split('#')[0] ?? '';
  cleaned = cleaned.replace(
    /\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi,
    '/[uuid]',
  );
  cleaned = cleaned.replace(/\/[0-9a-f]{12,}/gi, '/[hex]');
  cleaned = cleaned.replace(/\/\d+/g, '/[id]');
  return cleaned;
}

function percentile(values: readonly number[], pct: number): number {
  if (values.length === 0) return 0;
  if (values.length === 1) {
    const v = values[0];
    return typeof v === 'number' ? v : 0;
  }
  const sorted = values.slice().sort((a, b) => a - b);
  const rank = (pct / 100) * (sorted.length - 1);
  const lo = Math.floor(rank);
  const hi = Math.ceil(rank);
  const loVal = sorted[lo];
  const hiVal = sorted[hi];
  if (lo === hi || typeof hiVal !== 'number') return typeof loVal === 'number' ? loVal : 0;
  if (typeof loVal !== 'number') return hiVal;
  const frac = rank - lo;
  return loVal * (1 - frac) + hiVal * frac;
}

export function summariseApi(samples: readonly ApiSample[]) {
  const buckets = new Map<string, number[]>();
  for (const sample of samples) {
    const key = `${sample.method.toUpperCase()}|${templateEndpoint(sample.endpoint)}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(sample.duration_ms);
  }
  const keys = Array.from(buckets.keys()).sort();
  return keys.map((key) => {
    const [method, endpoint] = key.split('|');
    const durations = buckets.get(key) ?? [];
    return {
      endpoint: endpoint ?? '',
      method: method ?? '',
      count: durations.length,
      p50_ms: Math.round(percentile(durations, 50) * 100) / 100,
      p95_ms: Math.round(percentile(durations, 95) * 100) / 100,
      max_ms: Math.round(Math.max(...durations, 0) * 100) / 100,
    };
  });
}

// ---------------------------------------------------------------------------
// Per-route audit
// ---------------------------------------------------------------------------

// Exported for unit testing. Translates one Playwright `response` event
// into a NetworkResponseObservation and ingests it into the bucket state.
// Returns the observation it produced (useful for tests).
export async function handleResponseEvent(
  response: NetworkResponseHandle,
  state: ReturnType<typeof newCollectorState>,
): Promise<NetworkResponseObservation | null> {
  try {
    const req = response.request();
    const timing = req.timing();
    const durationMs =
      timing && typeof timing.responseEnd === 'number' && typeof timing.requestStart === 'number'
        ? Math.max(0, timing.responseEnd - timing.requestStart)
        : 0;
    const ctRaw = await response.headerValue('content-type');
    const ct = typeof ctRaw === 'string' ? ctRaw : '';
    const lenRaw = await response.headerValue('content-length');
    const transferBytes =
      typeof lenRaw === 'string' && /^\d+$/.test(lenRaw) ? Number.parseInt(lenRaw, 10) : 0;
    let decodedBytes = transferBytes;
    try {
      const body = await response.body();
      if (body && body.byteLength > 0) decodedBytes = body.byteLength;
    } catch {
      // Cross-origin responses may not expose body; transferBytes stands.
    }
    const obs: NetworkResponseObservation = {
      method: req.method(),
      url: response.url(),
      status: response.status(),
      durationMs,
      contentType: ct,
      transferSizeBytes: transferBytes,
      decodedSizeBytes: decodedBytes,
    };
    ingestObservation(obs, state);
    return obs;
  } catch {
    // Ignore individual response failures; the audit continues.
    return null;
  }
}

function captureResponses(
  page: AuditPerfPage,
  state: ReturnType<typeof newCollectorState>,
): () => void {
  const handler = async (response: NetworkResponseHandle): Promise<void> => {
    await handleResponseEvent(response, state);
  };
  page.on('response', handler);
  return () => page.off('response', handler);
}

async function auditRoute(
  browser: AuditPerfBrowser,
  cfg: AuditPerfRunConfig,
  route: string,
  now: () => Date,
): Promise<PerformancePageResult> {
  const url = urlFor(cfg.target, route);
  const started = Date.now();
  const pageSamples: PageMetricSample[] = [];
  const navSamples: NavStabilitySample[] = [];
  const networkState = newCollectorState();
  let error: string | null = null;
  let longTasks: ReturnType<typeof summariseLongTasks> = {
    count: 0,
    total_blocking_ms: 0,
    longest_ms: 0,
  };

  // 1) Page metrics — N independent loads.
  for (let i = 0; i < cfg.samples; i += 1) {
    const page = await browser.newPage();
    const detach = captureResponses(page, networkState);
    try {
      await page.evaluate(prepLongTaskObserver as never);
      const sample = await collectPageMetrics(page, {
        url,
        timeoutMs: cfg.request_timeout_ms,
      });
      pageSamples.push(sample);
      if (i === cfg.samples - 1) {
        // Capture long tasks on the last sample to avoid summing across pages.
        const raw = await page.evaluate<readonly { duration: number; startTime: number }[]>(
          readLongTaskEntries as never,
        );
        longTasks = summariseLongTasks(Array.isArray(raw) ? raw : []);
      }
    } catch (err) {
      error = (err as Error).message;
    } finally {
      detach();
    }
  }

  // 2) Repeated-nav stability — N back-to-back loads on a single page context.
  const navPage = await browser.newPage();
  try {
    for (let i = 0; i < cfg.repeated_nav_samples; i += 1) {
      try {
        await navPage.goto(url, { timeout: cfg.request_timeout_ms });
        await navPage.waitForLoadState('load');
        const rawSample = await navPage.evaluate<{
          js_heap_bytes: unknown;
          dom_node_count: unknown;
        } | null>(readNavSample as never);
        navSamples.push(
          normaliseNavSample(rawSample ?? { js_heap_bytes: null, dom_node_count: null }),
        );
      } catch (err) {
        error = error ?? (err as Error).message;
      }
    }
  } finally {
    // page is closed via browser.close() at the orchestrator level.
  }

  const pageMetrics = summarisePageMetrics(pageSamples);
  const apiEndpoints = summariseApi(networkState.apiSamples);
  const bundle = summariseBundle(networkState);

  return {
    route,
    url,
    fetched_at: now().toISOString(),
    page_metrics: pageMetrics,
    api_endpoints: apiEndpoints,
    api_samples: networkState.apiSamples,
    bundle,
    long_tasks: longTasks,
    nav_stability: {
      samples: navSamples,
      // Python recomputes the growth pct from samples — leave nulls here.
      dom_growth_pct: null,
      memory_growth_pct: null,
      memory_supported: navSamples.some((s) => s.js_heap_bytes !== null),
    },
    duration_ms: Date.now() - started,
    schema_version: PERF_RESULT_SCHEMA_VERSION,
    error,
  };
}

// ---------------------------------------------------------------------------
// Top-level orchestrator
// ---------------------------------------------------------------------------

export async function auditPerf(opts: AuditPerfOptions): Promise<AuditPerfResult> {
  if (!existsSync(opts.inputPath)) {
    throw new Error(`audit-perf: input path not found: ${opts.inputPath}`);
  }
  const raw = await readFile(opts.inputPath, 'utf-8');
  const cfg = loadRunConfig(JSON.parse(raw));
  await mkdir(cfg.out_dir, { recursive: true });

  const now = opts.now ?? (() => new Date());
  const browser = await opts.launcher();
  const pages: PerformancePageResult[] = [];
  let incomplete = false;

  try {
    for (const route of cfg.routes) {
      const result = await auditRoute(browser, cfg, route, now);
      pages.push(result);
      if (result.error !== null) incomplete = true;
      const perRoutePath = resolvePath(cfg.out_dir, `${routeSlug(route)}.json`);
      await writeFile(perRoutePath, JSON.stringify(result, null, 2) + '\n', 'utf-8');
    }
  } finally {
    await browser.close();
  }

  const outcome: PerformanceRunOutcome = { pages, incomplete };
  const indexPath = resolvePath(cfg.out_dir, 'index.json');
  await writeFile(indexPath, JSON.stringify(outcome, null, 2) + '\n', 'utf-8');
  return { outcome, indexPath };
}
