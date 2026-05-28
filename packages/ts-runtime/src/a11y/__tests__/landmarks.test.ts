import { describe, it, expect } from 'vitest';

import { detectLandmarkIssues, readLandmarkCounts } from '../landmarks.js';

describe('detectLandmarkIssues', () => {
  it('returns nothing for a compliant page', () => {
    const issues = detectLandmarkIssues({ main: 1, header: 1, nav: 1, footer: 1 });
    expect(issues).toEqual([]);
  });

  it('flags a missing main landmark', () => {
    const issues = detectLandmarkIssues({ main: 0, header: 1, nav: 1, footer: 1 });
    expect(issues).toHaveLength(1);
    expect(issues[0]?.landmark).toBe('main');
    expect(issues[0]?.category).toBe('missing-landmark');
  });

  it('flags duplicate main landmarks', () => {
    const issues = detectLandmarkIssues({ main: 2, header: 1, nav: 1, footer: 1 });
    expect(issues).toHaveLength(1);
    expect(issues[0]?.category).toBe('duplicate-landmark');
    expect(issues[0]?.description).toContain('2 <main>');
  });

  it('flags every missing recommended landmark', () => {
    const issues = detectLandmarkIssues({ main: 1, header: 0, nav: 0, footer: 0 });
    const landmarks = new Set(issues.map((i) => i.landmark));
    expect(landmarks).toEqual(new Set(['header', 'nav', 'footer']));
  });
});

describe('readLandmarkCounts', () => {
  it('aggregates counts from the page evaluation', async () => {
    const page = {
      evaluate: async <T>(fn: () => T | Promise<T>): Promise<T> => {
        const document = {
          querySelectorAll: (selector: string) => {
            const map: Record<string, number> = {
              "main, [role='main']": 1,
              "header, [role='banner']": 1,
              "nav, [role='navigation']": 0,
              "footer, [role='contentinfo']": 2,
            };
            return { length: map[selector] ?? 0 };
          },
        };
        (globalThis as unknown as { document: unknown }).document = document;
        try {
          return await fn();
        } finally {
          delete (globalThis as unknown as Record<string, unknown>)['document'];
        }
      },
    };
    const counts = await readLandmarkCounts(page);
    expect(counts).toEqual({ main: 1, header: 1, nav: 0, footer: 2 });
  });
});
