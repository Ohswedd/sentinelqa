// landmark structure check.
// Mirrors `modules/accessibility/checks/landmarks.py`: <main> required
// (exactly one), <header> / <nav> / <footer> recommended.

import type { LandmarkIssue } from './types.js';

export const REQUIRED_LANDMARKS: readonly string[] = ['main'];
export const RECOMMENDED_LANDMARKS: readonly string[] = ['header', 'nav', 'footer'];

export interface LandmarkCounts {
  readonly main: number;
  readonly header: number;
  readonly nav: number;
  readonly footer: number;
}

export function detectLandmarkIssues(counts: LandmarkCounts): LandmarkIssue[] {
  const issues: LandmarkIssue[] = [];
  for (const lm of REQUIRED_LANDMARKS) {
    const count = (counts as unknown as Record<string, number>)[lm] ?? 0;
    if (count === 0) {
      issues.push({
        category: 'missing-landmark',
        landmark: lm,
        description: `Automated accessibility check found no <${lm}> landmark on the page.`,
      });
    } else if (count > 1) {
      issues.push({
        category: 'duplicate-landmark',
        landmark: lm,
        description: `Automated accessibility check found ${count} <${lm}> landmarks; exactly one is required.`,
      });
    }
  }
  for (const lm of RECOMMENDED_LANDMARKS) {
    const count = (counts as unknown as Record<string, number>)[lm] ?? 0;
    if (count === 0) {
      issues.push({
        category: 'missing-landmark',
        landmark: lm,
        description: `Automated accessibility check found no <${lm}> landmark on the page (recommended).`,
      });
    }
  }
  return issues;
}

export interface LandmarkPageLike {
  evaluate<T>(fn: () => T | Promise<T>): Promise<T>;
}

export async function readLandmarkCounts(page: LandmarkPageLike): Promise<LandmarkCounts> {
  return await page.evaluate(() => {
    const countOf = (selector: string): number => document.querySelectorAll(selector).length;
    return {
      main: countOf("main, [role='main']"),
      header: countOf("header, [role='banner']"),
      nav: countOf("nav, [role='navigation']"),
      footer: countOf("footer, [role='contentinfo']"),
    };
  });
}
