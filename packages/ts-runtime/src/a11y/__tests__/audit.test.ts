import { mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { auditA11y, loadRunConfig, routeSlug, type AuditA11yLauncher } from '../audit.js';

interface StubPageOpts {
  readonly axeViolations?: readonly Record<string, unknown>[];
  readonly landmarkCounts?: { main: number; header: number; nav: number; footer: number };
  readonly samples?: readonly Record<string, unknown>[];
  readonly focusSamples?: readonly Record<string, unknown>[];
  readonly throwOnNavigation?: Error;
}

const makeStubPage = (opts: StubPageOpts) => {
  let evalCount = 0;
  return {
    async goto(_url: string) {
      if (opts.throwOnNavigation) throw opts.throwOnNavigation;
    },
    url() {
      return 'http://stub.test/';
    },
    async addScriptTag(_: { content: string }) {
      return undefined;
    },
    async evaluate<T>(_fn: unknown, _arg?: unknown): Promise<T> {
      evalCount += 1;
      switch (evalCount) {
        case 1:
          return { violations: opts.axeViolations ?? [] } as unknown as T;
        case 2:
          return (opts.landmarkCounts ?? { main: 1, header: 1, nav: 1, footer: 1 }) as unknown as T;
        case 3:
          return (opts.samples ?? []) as unknown as T;
        default:
          // walkFocus calls evaluate per Tab; return null to stop the walk.
          return null as unknown as T;
      }
    },
    keyboard: {
      async press(_: string) {
        return undefined;
      },
    },
  };
};

const makeLauncher =
  (opts: StubPageOpts): AuditA11yLauncher =>
  async () => {
    const page = makeStubPage(opts);
    return {
      async newPage() {
        return page as unknown as Awaited<
          ReturnType<AuditA11yLauncher>
        >['newPage'] extends () => Promise<infer P>
          ? P
          : never;
      },
      async close() {
        return undefined;
      },
    };
  };

describe('loadRunConfig', () => {
  it('round-trips a valid config', () => {
    const cfg = loadRunConfig({
      schema_version: '1',
      run_id: 'RUN-1',
      target: 'http://localhost:3000',
      out_dir: '/tmp/x',
      routes: ['/'],
      axe_tags: ['wcag2a'],
      request_timeout_ms: 30000,
      keyboard_max_tabs: 50,
    });
    expect(cfg.routes).toEqual(['/']);
  });

  it('rejects non-object input', () => {
    expect(() => loadRunConfig([])).toThrow(/JSON object/);
  });

  it('rejects empty string keys', () => {
    expect(() =>
      loadRunConfig({
        run_id: '',
        target: 'http://localhost',
        out_dir: '/tmp/x',
        routes: ['/'],
        axe_tags: ['wcag2a'],
        request_timeout_ms: 30000,
        keyboard_max_tabs: 50,
      }),
    ).toThrow();
  });

  it('rejects empty arrays', () => {
    expect(() =>
      loadRunConfig({
        run_id: 'RUN-1',
        target: 'http://localhost',
        out_dir: '/tmp/x',
        routes: [],
        axe_tags: ['wcag2a'],
        request_timeout_ms: 30000,
        keyboard_max_tabs: 50,
      }),
    ).toThrow();
  });
});

describe('routeSlug', () => {
  it.each([
    ['/', 'root'],
    ['', 'root'],
    ['/dashboard', 'dashboard'],
    ['/users/123', 'users-123'],
    ['/settings/foo bar', 'settings-foo-bar'],
  ])('slugs %s → %s', (input, expected) => {
    expect(routeSlug(input)).toBe(expected);
  });
});

describe('auditA11y', () => {
  let workdir: string;
  beforeEach(async () => {
    workdir = join(tmpdir(), `audit-a11y-${Date.now()}-${Math.random()}`);
    await mkdir(workdir, { recursive: true });
  });
  afterEach(async () => {
    await rm(workdir, { recursive: true, force: true });
  });

  const writeConfig = async (overrides: Partial<Record<string, unknown>> = {}) => {
    const cfg = {
      schema_version: '1',
      run_id: 'RUN-AAAAAAAAAAAA',
      target: 'http://localhost:3000',
      out_dir: workdir,
      routes: ['/'],
      axe_tags: ['wcag2a'],
      request_timeout_ms: 30000,
      keyboard_max_tabs: 50,
      ...overrides,
    };
    const p = join(workdir, 'run-config.json');
    await writeFile(p, JSON.stringify(cfg), 'utf-8');
    return p;
  };

  it('writes per-route JSON + index for a compliant fixture', async () => {
    const cfg = await writeConfig();
    const launcher = makeLauncher({});
    const result = await auditA11y({ inputPath: cfg, launcher, axeSource: '// stub' });
    expect(result.outcome.pages).toHaveLength(1);
    expect(result.outcome.pages[0]?.axe_violations).toEqual([]);
    const index = JSON.parse(await readFile(result.indexPath, 'utf-8'));
    expect(index.pages).toHaveLength(1);
    const perRoute = JSON.parse(await readFile(join(workdir, 'root.json'), 'utf-8'));
    expect(perRoute.route).toBe('/');
  });

  it('records axe violations + landmark misses for a broken fixture', async () => {
    const cfg = await writeConfig();
    const launcher = makeLauncher({
      axeViolations: [
        {
          id: 'image-alt',
          impact: 'critical',
          tags: ['wcag2a'],
          help: 'help',
          helpUrl: 'https://example.test/image-alt',
          description: 'desc',
          nodes: [{ target: ['img'], html: '<img>', failureSummary: 'no alt' }],
        },
      ],
      landmarkCounts: { main: 0, header: 0, nav: 0, footer: 0 },
      samples: [
        {
          role: 'button',
          selector: '#icon',
          ariaLabel: '',
          ariaLabelledbyText: '',
          labelText: '',
          visibleText: '',
          title: '',
          placeholder: '',
        },
      ],
    });
    const result = await auditA11y({ inputPath: cfg, launcher, axeSource: '// stub' });
    const page = result.outcome.pages[0];
    expect(page?.axe_violations.map((v) => v.rule_id)).toEqual(['image-alt']);
    expect(page?.landmark_issues.length).toBeGreaterThanOrEqual(4); // missing main + header + nav + footer
    expect(page?.accessible_name_issues).toHaveLength(1);
  });

  it('marks the run as incomplete when a route navigation throws', async () => {
    const cfg = await writeConfig();
    const launcher = makeLauncher({ throwOnNavigation: new Error('net::ERR_FAILED') });
    const result = await auditA11y({ inputPath: cfg, launcher, axeSource: '// stub' });
    expect(result.outcome.incomplete).toBe(true);
    expect(result.outcome.pages[0]?.error).toContain('net::ERR_FAILED');
  });

  it('raises when the input file is missing', async () => {
    const launcher = makeLauncher({});
    await expect(auditA11y({ inputPath: join(workdir, 'nope.json'), launcher })).rejects.toThrow(
      /input path not found/,
    );
  });
});
