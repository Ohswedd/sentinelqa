import { describe, it, expect } from 'vitest';

import {
  AxeCoreNotInstalledError,
  DefaultAxeSourceResolver,
  normaliseViolations,
  runAxe,
} from '../axe.js';

describe('normaliseViolations', () => {
  it('returns an empty list for empty input', () => {
    expect(normaliseViolations([])).toEqual([]);
  });

  it('skips entries missing an id', () => {
    expect(normaliseViolations([{ impact: 'serious' }])).toEqual([]);
  });

  it('maps a full axe violation into typed shape', () => {
    const raw = [
      {
        id: 'color-contrast',
        impact: 'serious',
        tags: ['wcag2aa', 'cat.color'],
        help: 'Contrast too low',
        helpUrl: 'https://example.test/color-contrast',
        description: 'Elements must have sufficient color contrast',
        nodes: [
          {
            target: ['p.warning'],
            html: '<p class="warning">',
            failureSummary: 'Fix the foreground/background contrast',
          },
        ],
      },
    ];
    const out = normaliseViolations(raw);
    expect(out).toHaveLength(1);
    const v = out[0];
    expect(v).toBeDefined();
    if (!v) throw new Error('expected violation');
    expect(v.rule_id).toBe('color-contrast');
    expect(v.impact).toBe('serious');
    expect(v.tags).toEqual(['wcag2aa', 'cat.color']);
    expect(v.experimental).toBe(false);
    expect(v.nodes[0]?.target).toEqual(['p.warning']);
  });

  it('marks experimental rules', () => {
    const out = normaliseViolations([
      { id: 'scrollable-region-focusable', impact: 'moderate', tags: ['experimental'], nodes: [] },
    ]);
    expect(out[0]?.experimental).toBe(true);
  });

  it('coerces non-string target to []', () => {
    const out = normaliseViolations([
      { id: 'x', impact: 'minor', tags: [], nodes: [{ target: [123, 'ok'] }] },
    ]);
    expect(out[0]?.nodes[0]?.target).toEqual(['ok']);
  });

  it('accepts a single-string target', () => {
    const out = normaliseViolations([
      { id: 'x', impact: 'minor', tags: [], nodes: [{ target: 'body' }] },
    ]);
    expect(out[0]?.nodes[0]?.target).toEqual(['body']);
  });

  it('defaults unknown impact to moderate', () => {
    const out = normaliseViolations([{ id: 'x', impact: 'bogus', tags: [], nodes: [] }]);
    expect(out[0]?.impact).toBe('moderate');
  });
});

describe('runAxe', () => {
  it('injects the supplied axe source and returns the page evaluation result', async () => {
    const calls: string[] = [];
    const page = {
      addScriptTag: async (opts: { content: string }) => {
        calls.push('addScriptTag');
        expect(opts.content).toBe('// axe stub');
      },
      evaluate: async <T>(
        fn: (tags: readonly string[]) => Promise<T> | T,
        arg: readonly string[],
      ) => {
        calls.push('evaluate');
        // Provide a window.axe shim and execute the page-side function.
        (globalThis as unknown as { window: unknown; document: unknown }).window = {
          axe: {
            run: async () => ({ violations: [{ id: 'color-contrast' }] }),
          },
        };
        (globalThis as unknown as { document: unknown }).document = {};
        try {
          return await fn(arg);
        } finally {
          delete (globalThis as unknown as Record<string, unknown>)['window'];
          delete (globalThis as unknown as Record<string, unknown>)['document'];
        }
      },
    };
    const result = await runAxe(page, { tags: ['wcag2a'], axeSourceOverride: '// axe stub' });
    expect(result.violations).toHaveLength(1);
    expect(calls).toEqual(['addScriptTag', 'evaluate']);
  });

  it('returns no violations when axe is not on window', async () => {
    const page = {
      addScriptTag: async () => undefined,
      evaluate: async <T>(
        fn: (tags: readonly string[]) => Promise<T> | T,
        arg: readonly string[],
      ) => {
        (globalThis as unknown as { window: unknown; document: unknown }).window = {};
        (globalThis as unknown as { document: unknown }).document = {};
        try {
          return await fn(arg);
        } finally {
          delete (globalThis as unknown as Record<string, unknown>)['window'];
          delete (globalThis as unknown as Record<string, unknown>)['document'];
        }
      },
    };
    const result = await runAxe(page, { axeSourceOverride: '// stub' });
    expect(result.violations).toEqual([]);
  });
});

describe('DefaultAxeSourceResolver', () => {
  it('raises a typed error when axe-core is not installed', async () => {
    const resolver = new DefaultAxeSourceResolver();
    // axe-core is intentionally NOT a dependency of @sentinelqa/ts-runtime
    // — this test verifies the error path.
    await expect(resolver.resolveSource()).rejects.toBeInstanceOf(AxeCoreNotInstalledError);
  });
});
