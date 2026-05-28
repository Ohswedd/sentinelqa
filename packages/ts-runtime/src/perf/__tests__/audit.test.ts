import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { loadRunConfig, routeSlug, summariseApi, summarisePageMetrics, urlFor } from '../audit.js';
import { auditPerf, type AuditPerfBrowser, type AuditPerfPage } from '../audit.js';
import type { ApiSample, PageMetricSample } from '../types.js';

describe('routeSlug', () => {
  it('returns root for / and ""', () => {
    expect(routeSlug('/')).toBe('root');
    expect(routeSlug('')).toBe('root');
  });
  it('replaces unsafe characters with dashes', () => {
    expect(routeSlug('/users/42')).toBe('users-42');
  });
});

describe('urlFor', () => {
  it('joins target and route', () => {
    expect(urlFor('http://x', '/foo')).toBe('http://x/foo');
    expect(urlFor('http://x/', '/foo')).toBe('http://x/foo');
    expect(urlFor('http://x/', 'foo')).toBe('http://x/foo');
  });
  it('preserves absolute URLs', () => {
    expect(urlFor('http://x', 'https://y/foo')).toBe('https://y/foo');
  });
});

describe('summarisePageMetrics', () => {
  it('computes median per metric', () => {
    const samples: PageMetricSample[] = [
      {
        lcp_ms: 1000,
        cls: 0.01,
        inp_ms: null,
        ttfb_ms: 80,
        dcl_ms: 200,
        load_ms: 500,
      },
      {
        lcp_ms: 2000,
        cls: 0.02,
        inp_ms: 150,
        ttfb_ms: 100,
        dcl_ms: 250,
        load_ms: 600,
      },
      {
        lcp_ms: 3000,
        cls: 0.03,
        inp_ms: 180,
        ttfb_ms: 120,
        dcl_ms: 300,
        load_ms: 700,
      },
    ];
    const summary = summarisePageMetrics(samples);
    expect(summary.median_lcp_ms).toBe(2000);
    expect(summary.median_cls).toBeCloseTo(0.02);
    expect(summary.median_inp_ms).toBe(165); // median of [150, 180] = 165
    expect(summary.inp_supported).toBe(true);
  });
  it('reports inp_supported=false when no INP observed', () => {
    const samples: PageMetricSample[] = [
      {
        lcp_ms: 1000,
        cls: 0.01,
        inp_ms: null,
        ttfb_ms: 100,
        dcl_ms: 200,
        load_ms: 500,
      },
    ];
    const summary = summarisePageMetrics(samples);
    expect(summary.inp_supported).toBe(false);
    expect(summary.median_inp_ms).toBe(null);
  });
});

describe('summariseApi', () => {
  it('groups by templated endpoint + method', () => {
    const samples: ApiSample[] = [
      { endpoint: '/api/users/42', method: 'get', duration_ms: 50, status: 200 },
      { endpoint: '/api/users/99', method: 'GET', duration_ms: 70, status: 200 },
      { endpoint: '/api/users', method: 'POST', duration_ms: 200, status: 201 },
    ];
    const summaries = summariseApi(samples);
    expect(summaries).toHaveLength(2);
    // Sorted alphabetically by "<METHOD>|<endpoint>" key:
    // GET|/api/users/[id]  <  POST|/api/users
    expect(summaries[0]?.endpoint).toBe('/api/users/[id]');
    expect(summaries[0]?.method).toBe('GET');
    expect(summaries[0]?.count).toBe(2);
    expect(summaries[1]?.endpoint).toBe('/api/users');
    expect(summaries[1]?.method).toBe('POST');
  });
});

describe('loadRunConfig', () => {
  it('parses a valid object', () => {
    const cfg = loadRunConfig({
      schema_version: '1',
      run_id: 'RUN-1',
      target: 'http://localhost:3000',
      out_dir: '/tmp/out',
      routes: ['/'],
      samples: 3,
      repeated_nav_samples: 5,
      request_timeout_ms: 30000,
      api_path_allowlist: ['/api/'],
    });
    expect(cfg.samples).toBe(3);
    expect(cfg.repeated_nav_samples).toBe(5);
    expect(cfg.api_path_allowlist).toEqual(['/api/']);
  });
  it('rejects empty routes', () => {
    expect(() =>
      loadRunConfig({
        schema_version: '1',
        run_id: 'RUN-1',
        target: 'http://localhost:3000',
        out_dir: '/tmp/out',
        routes: [],
        samples: 3,
        repeated_nav_samples: 5,
        request_timeout_ms: 30000,
      }),
    ).toThrow(/must contain at least one entry/);
  });
  it('rejects repeated_nav_samples < 2', () => {
    expect(() =>
      loadRunConfig({
        schema_version: '1',
        run_id: 'RUN-1',
        target: 'http://localhost:3000',
        out_dir: '/tmp/out',
        routes: ['/'],
        samples: 3,
        repeated_nav_samples: 1,
        request_timeout_ms: 30000,
      }),
    ).toThrow(/integer >= 2/);
  });
  it('rejects non-object input', () => {
    expect(() => loadRunConfig(null)).toThrow(/must be a JSON object/);
  });
});

// ---------------------------------------------------------------------------
// auditPerf end-to-end with deterministic stub browser
// ---------------------------------------------------------------------------

function stubPage(metric: { lcp_ms: number; cls: number; ttfb_ms: number }): AuditPerfPage {
  const evalCalls: number[] = [];
  return {
    evaluate: (async (_fn: never, ..._args: never[]) => {
      evalCalls.push(evalCalls.length);
      // 1st call: prep observers (returns undefined)
      // 2nd call: prep long-task observer
      // 3rd call: read metrics
      // For the nav-sample page, calls alternate goto/eval per visit.
      if (evalCalls.length === 1) return undefined;
      if (evalCalls.length === 2) return undefined;
      if (evalCalls.length === 3) {
        return {
          lcp_ms: metric.lcp_ms,
          cls: metric.cls,
          inp_ms: null,
          ttfb_ms: metric.ttfb_ms,
          dcl_ms: 400,
          load_ms: 900,
        };
      }
      // long-task read
      if (evalCalls.length === 4) return [];
      // nav samples — return small steady values
      return { js_heap_bytes: 1024, dom_node_count: 200 };
    }) as never,
    goto: (async () => undefined) as never,
    waitForLoadState: async () => undefined,
    url: () => 'http://localhost:3000/',
    on: () => undefined,
    off: () => undefined,
  };
}

describe('auditPerf', () => {
  it('writes per-route + index artifacts for a single route', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'perf-audit-'));
    const inputPath = join(dir, 'run-config.json');
    await writeFile(
      inputPath,
      JSON.stringify({
        schema_version: '1',
        run_id: 'RUN-1',
        target: 'http://localhost:3000',
        out_dir: dir,
        routes: ['/'],
        samples: 1,
        repeated_nav_samples: 2,
        request_timeout_ms: 30000,
      }),
      'utf-8',
    );
    const browser: AuditPerfBrowser = {
      newPage: async () => stubPage({ lcp_ms: 1500, cls: 0.02, ttfb_ms: 100 }),
      close: async () => undefined,
    };
    const result = await auditPerf({
      inputPath,
      launcher: async () => browser,
      now: () => new Date('2026-05-28T00:00:00Z'),
    });
    expect(result.outcome.pages).toHaveLength(1);
    const page = result.outcome.pages[0]!;
    expect(page.route).toBe('/');
    expect(page.schema_version).toBe('1');
    const persisted = JSON.parse(await readFile(result.indexPath, 'utf-8')) as {
      pages: unknown[];
      incomplete: boolean;
    };
    expect(persisted.pages).toHaveLength(1);
    expect(persisted.incomplete).toBe(false);
  });

  it('throws when the input file is missing', async () => {
    await expect(
      auditPerf({
        inputPath: '/nonexistent/perf-config.json',
        launcher: async () => ({
          newPage: async () => stubPage({ lcp_ms: 1, cls: 0, ttfb_ms: 0 }),
          close: async () => undefined,
        }),
      }),
    ).rejects.toThrow(/input path not found/);
  });
});
