import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { normaliseSample, prepObservers, readObservers } from '../page_metrics.js';

describe('normaliseSample', () => {
  it('passes through valid observations', () => {
    const sample = normaliseSample({
      lcp_ms: 1500,
      cls: 0.05,
      inp_ms: 200,
      ttfb_ms: 100,
      dcl_ms: 400,
      load_ms: 900,
    });
    expect(sample.lcp_ms).toBe(1500);
    expect(sample.cls).toBe(0.05);
    expect(sample.inp_ms).toBe(200);
  });

  it('clamps values above the upper bound', () => {
    const sample = normaliseSample({
      lcp_ms: 1_000_000,
      cls: 999,
      inp_ms: 200,
      ttfb_ms: null,
      dcl_ms: null,
      load_ms: null,
    });
    expect(sample.lcp_ms).toBe(120_000);
    expect(sample.cls).toBe(10);
  });

  it('converts null/NaN/Infinity to null', () => {
    const sample = normaliseSample({
      lcp_ms: null,
      cls: Number.NaN,
      inp_ms: Number.POSITIVE_INFINITY,
      ttfb_ms: null,
      dcl_ms: null,
      load_ms: null,
    });
    expect(sample).toEqual({
      lcp_ms: null,
      cls: null,
      inp_ms: null,
      ttfb_ms: null,
      dcl_ms: null,
      load_ms: null,
    });
  });

  it('clamps negative values to zero', () => {
    const sample = normaliseSample({
      lcp_ms: -1,
      cls: -1,
      inp_ms: -1,
      ttfb_ms: -1,
      dcl_ms: -1,
      load_ms: -1,
    });
    expect(sample).toEqual({
      lcp_ms: 0,
      cls: 0,
      inp_ms: 0,
      ttfb_ms: 0,
      dcl_ms: 0,
      load_ms: 0,
    });
  });
});

// ---------------------------------------------------------------------------
// In-page helpers (prepObservers / readObservers) — these normally run inside
// a real Chromium tab. We stub the necessary browser globals so the helpers
// can be exercised in node-environment vitest.
// ---------------------------------------------------------------------------

type Cb = (list: { getEntries: () => unknown[] }) => void;
interface FakeObserverState {
  lastInit: PerformanceObserverInit | null;
  cb: Cb | null;
}

function installFakeWindow(): {
  cleanup: () => void;
  observers: FakeObserverState;
  fireLcp: (startTime: number) => void;
  fireCls: (value: number, hadRecentInput?: boolean) => void;
  fireInp: (duration: number) => void;
  setNav: (
    nav: { responseStart: number; domContentLoadedEventEnd: number; loadEventEnd: number } | null,
  ) => void;
} {
  const observers: FakeObserverState = { lastInit: null, cb: null };
  const allCbs: { type: string; cb: Cb }[] = [];
  class FakePerformanceObserver {
    private readonly cb: Cb;
    constructor(cb: Cb) {
      this.cb = cb;
      observers.cb = cb;
    }
    observe(init: PerformanceObserverInit): void {
      observers.lastInit = init;
      allCbs.push({ type: init.type ?? 'unknown', cb: this.cb });
    }
  }
  const originalPO = (globalThis as { PerformanceObserver?: unknown }).PerformanceObserver;
  (globalThis as { PerformanceObserver?: unknown }).PerformanceObserver =
    FakePerformanceObserver as unknown as typeof PerformanceObserver;

  const w = globalThis as unknown as {
    window?: unknown;
    performance?: unknown;
  };
  const originalWindow = w.window;
  const originalPerf = w.performance;
  let navEntry: {
    responseStart: number;
    domContentLoadedEventEnd: number;
    loadEventEnd: number;
  } | null = null;
  w.window = globalThis;
  w.performance = {
    getEntriesByType: (kind: string) => (kind === 'navigation' && navEntry ? [navEntry] : []),
  } as unknown as Performance;

  const fire = (type: string, entries: unknown[]): void => {
    for (const item of allCbs) {
      if (item.type === type) item.cb({ getEntries: () => entries });
    }
  };

  return {
    cleanup: () => {
      (globalThis as { PerformanceObserver?: unknown }).PerformanceObserver = originalPO;
      w.window = originalWindow;
      w.performance = originalPerf;
    },
    observers,
    fireLcp: (startTime) => fire('largest-contentful-paint', [{ startTime }]),
    fireCls: (value, hadRecentInput = false) => fire('layout-shift', [{ value, hadRecentInput }]),
    fireInp: (duration) => fire('event', [{ duration }]),
    setNav: (nav) => {
      navEntry = nav;
    },
  };
}

describe('prepObservers + readObservers', () => {
  let fake: ReturnType<typeof installFakeWindow>;
  beforeEach(() => {
    fake = installFakeWindow();
  });
  afterEach(() => {
    fake.cleanup();
    delete (globalThis as unknown as { __sentinelPerf?: unknown }).__sentinelPerf;
  });

  it('reads zeros when no observer fires and no navigation entry exists', () => {
    prepObservers();
    const got = readObservers();
    expect(got.lcp_ms).toBe(null);
    expect(got.cls).toBe(0);
    expect(got.inp_ms).toBe(null);
    expect(got.ttfb_ms).toBe(null);
    expect(got.dcl_ms).toBe(null);
    expect(got.load_ms).toBe(null);
  });

  it('accumulates LCP, CLS, INP from observer fires + navigation entry', () => {
    prepObservers();
    fake.fireLcp(2400);
    fake.fireCls(0.03);
    fake.fireCls(0.02);
    fake.fireInp(180);
    fake.setNav({ responseStart: 80, domContentLoadedEventEnd: 300, loadEventEnd: 600 });
    const got = readObservers();
    expect(got.lcp_ms).toBe(2400);
    expect(got.cls).toBeCloseTo(0.05);
    expect(got.inp_ms).toBe(180);
    expect(got.ttfb_ms).toBe(80);
    expect(got.dcl_ms).toBe(300);
    expect(got.load_ms).toBe(600);
  });

  it('ignores layout-shift entries with hadRecentInput=true', () => {
    prepObservers();
    fake.fireCls(0.5, true);
    expect(readObservers().cls).toBe(0);
  });

  it('zero load/dcl values become null', () => {
    prepObservers();
    fake.setNav({ responseStart: 0, domContentLoadedEventEnd: 0, loadEventEnd: 0 });
    const got = readObservers();
    expect(got.dcl_ms).toBe(null);
    expect(got.load_ms).toBe(null);
  });

  it('survives PerformanceObserver constructor failures', () => {
    const w = globalThis as unknown as { PerformanceObserver: unknown };
    w.PerformanceObserver = vi.fn(() => {
      throw new Error('unsupported');
    }) as unknown as typeof PerformanceObserver;
    expect(() => prepObservers()).not.toThrow();
  });
});
