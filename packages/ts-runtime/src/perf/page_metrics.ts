// Phase 12.02 — collect synthetic page-level performance metrics.
//
// `collectPageMetrics` is called once per (route, sample) pair. It
// installs PerformanceObservers BEFORE navigation, navigates, waits
// for the page to be idle, and reads the metrics back. The returned
// shape mirrors Pydantic's PageMetricSample.
//
// CLAUDE §27: these are synthetic lab measurements; they are never
// Real-User Monitoring. The Python side carries that label through
// to the user.

import type { PageMetricSample } from './types.js';

export interface PageMetricsCollectorPage {
  evaluate<T>(fn: (...args: never[]) => T | Promise<T>, ...args: never[]): Promise<T>;
  goto(url: string, opts?: { timeout?: number; waitUntil?: string }): Promise<unknown>;
  waitForLoadState(state: 'load' | 'domcontentloaded' | 'networkidle'): Promise<void>;
  url(): string;
}

export interface CollectPageMetricsOptions {
  readonly url: string;
  readonly timeoutMs: number;
  readonly waitForNetworkIdle?: boolean;
}

// `prepObservers` runs inside the page BEFORE navigation. It installs
// PerformanceObservers that stash running totals on `window`. The matching
// `readObservers` reads those totals once the page has loaded.
export function prepObservers(): void {
  const w = window as unknown as {
    __sentinelPerf?: { lcp: number | null; cls: number; inp: number | null };
  };
  w.__sentinelPerf = { lcp: null, cls: 0, inp: null };
  try {
    const lcpObs = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      if (entries.length === 0) return;
      const last = entries[entries.length - 1];
      if (last && typeof last.startTime === 'number') {
        w.__sentinelPerf!.lcp = last.startTime;
      }
    });
    lcpObs.observe({ type: 'largest-contentful-paint', buffered: true });
  } catch {
    /* unsupported */
  }
  try {
    const clsObs = new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & {
        value?: number;
        hadRecentInput?: boolean;
      })[]) {
        if (!entry.hadRecentInput) {
          w.__sentinelPerf!.cls += entry.value ?? 0;
        }
      }
    });
    clsObs.observe({ type: 'layout-shift', buffered: true });
  } catch {
    /* unsupported */
  }
  try {
    const inpObs = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const dur = entry.duration ?? 0;
        if (w.__sentinelPerf!.inp === null || dur > w.__sentinelPerf!.inp) {
          w.__sentinelPerf!.inp = dur;
        }
      }
    });
    // `durationThreshold` is part of the Event-Timing API spec but not in
    // baseline lib.dom.d.ts; cast through `unknown` rather than `as any`
    // so eslint's no-any rule is satisfied.
    inpObs.observe({
      type: 'event',
      buffered: true,
      durationThreshold: 16,
    } as unknown as PerformanceObserverInit);
  } catch {
    /* not supported in this browser */
  }
}

export function readObservers(): {
  lcp_ms: number | null;
  cls: number;
  inp_ms: number | null;
  ttfb_ms: number | null;
  dcl_ms: number | null;
  load_ms: number | null;
} {
  const w = window as unknown as {
    __sentinelPerf?: { lcp: number | null; cls: number; inp: number | null };
  };
  const perfState = w.__sentinelPerf ?? { lcp: null, cls: 0, inp: null };
  const navEntries = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[];
  const nav = navEntries.length > 0 ? navEntries[0] : null;
  const ttfb = nav ? nav.responseStart : null;
  const dcl = nav ? nav.domContentLoadedEventEnd : null;
  const load = nav ? nav.loadEventEnd : null;
  return {
    lcp_ms: perfState.lcp,
    cls: perfState.cls,
    inp_ms: perfState.inp,
    ttfb_ms: ttfb,
    dcl_ms: dcl !== null && dcl > 0 ? dcl : null,
    load_ms: load !== null && load > 0 ? load : null,
  };
}

function clampNumber(value: unknown, min: number, max: number): number | null {
  if (typeof value !== 'number' || Number.isNaN(value)) return null;
  if (!Number.isFinite(value)) return null;
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

export interface RawObserverPayload {
  lcp_ms: unknown;
  cls: unknown;
  inp_ms: unknown;
  ttfb_ms: unknown;
  dcl_ms: unknown;
  load_ms: unknown;
}

export function normaliseSample(raw: RawObserverPayload): PageMetricSample {
  return {
    lcp_ms: clampNumber(raw.lcp_ms, 0, 120_000),
    cls: clampNumber(raw.cls, 0, 10),
    inp_ms: clampNumber(raw.inp_ms, 0, 120_000),
    ttfb_ms: clampNumber(raw.ttfb_ms, 0, 120_000),
    dcl_ms: clampNumber(raw.dcl_ms, 0, 120_000),
    load_ms: clampNumber(raw.load_ms, 0, 120_000),
  };
}

export async function collectPageMetrics(
  page: PageMetricsCollectorPage,
  opts: CollectPageMetricsOptions,
): Promise<PageMetricSample> {
  await page.evaluate(prepObservers as never);
  await page.goto(opts.url, { timeout: opts.timeoutMs });
  if (opts.waitForNetworkIdle) {
    await page.waitForLoadState('networkidle');
  } else {
    await page.waitForLoadState('load');
  }
  const raw = await page.evaluate<RawObserverPayload | null>(readObservers as never);
  return normaliseSample(
    raw ?? {
      lcp_ms: null,
      cls: null,
      inp_ms: null,
      ttfb_ms: null,
      dcl_ms: null,
      load_ms: null,
    },
  );
}
