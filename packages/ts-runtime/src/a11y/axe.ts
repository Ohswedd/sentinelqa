// Phase 11 (PRD §10.4, ADR-0016) — axe-core integration.
//
// The helper injects axe-core into a Playwright `Page` and runs the
// configured rule set. The axe-core source is resolved from
// `node_modules/axe-core/axe.min.js` at runtime — when the project has
// not added the dependency, the helper throws a clear, typed error.
//
// Tests inject the source via the `axeSourceOverride` option so the
// pure DOM + axe path is exercised without requiring axe-core to be
// installed in the workspace's lockfile.
//
// CLAUDE §28: this helper never makes a full-compliance claim — it
// returns axe violations only. Compliance language belongs to humans.

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

import type { AxeViolation } from './types.js';

const require = createRequire(import.meta.url);

export interface AxeSourceResolver {
  /** Return axe-core's `axe.min.js` source as a string. */
  resolveSource(): Promise<string>;
}

export class DefaultAxeSourceResolver implements AxeSourceResolver {
  async resolveSource(): Promise<string> {
    let resolvedPath: string;
    try {
      resolvedPath = require.resolve('axe-core/axe.min.js');
    } catch {
      throw new AxeCoreNotInstalledError(
        'axe-core is not installed. Run `pnpm add axe-core` in the workspace ' +
          'that hosts this Playwright runner.',
      );
    }
    return readFile(resolvedPath, 'utf-8');
  }
}

export class AxeCoreNotInstalledError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AxeCoreNotInstalledError';
  }
}

export interface PageLike {
  addScriptTag(opts: { content: string }): Promise<unknown>;
  evaluate<T>(
    fn: (axeTags: readonly string[]) => Promise<T> | T,
    arg: readonly string[],
  ): Promise<T>;
}

export interface RunAxeOptions {
  readonly tags?: readonly string[];
  readonly sourceResolver?: AxeSourceResolver;
  readonly axeSourceOverride?: string;
}

export interface RawAxeRunResult {
  readonly violations: readonly Record<string, unknown>[];
}

/**
 * Inject axe-core into the page and run `axe.run` with the requested
 * tags. Returns the raw axe-core response so the Python side can
 * normalise it via `engine.modules.accessibility.axe_runner`.
 */
export async function runAxe(page: PageLike, opts: RunAxeOptions = {}): Promise<RawAxeRunResult> {
  const tags = opts.tags ?? ['wcag2a', 'wcag2aa', 'best-practice'];
  const source =
    opts.axeSourceOverride ??
    (await (opts.sourceResolver ?? new DefaultAxeSourceResolver()).resolveSource());
  await page.addScriptTag({ content: source });
  const raw = await page.evaluate<RawAxeRunResult>(
    // The function executes inside the page. `axe` is attached to the
    // window by the injected source.
    async (axeTags) => {
      const w = window as unknown as {
        axe?: { run: (ctx: unknown, opts: unknown) => Promise<unknown> };
      };
      if (typeof w.axe?.run !== 'function') {
        return { violations: [] };
      }
      const result = (await w.axe.run(document, {
        runOnly: { type: 'tag', values: Array.from(axeTags) },
        resultTypes: ['violations'],
      })) as { violations?: unknown };
      return {
        violations: Array.isArray(result.violations)
          ? (result.violations as Record<string, unknown>[])
          : [],
      };
    },
    tags,
  );
  return raw;
}

/**
 * Map a raw axe-core violation list to typed `AxeViolation` records.
 * Mirrors `modules/accessibility/axe_runner.axe_violations_from_list`.
 */
export function normaliseViolations(raw: readonly Record<string, unknown>[]): AxeViolation[] {
  const valid: ReadonlySet<string> = new Set(['critical', 'serious', 'moderate', 'minor']);
  const out: AxeViolation[] = [];
  for (const entry of raw) {
    if (typeof entry !== 'object' || entry === null) continue;
    const ruleId = typeof entry['id'] === 'string' ? entry['id'] : '';
    if (!ruleId) continue;
    const impactRaw = typeof entry['impact'] === 'string' ? entry['impact'] : 'moderate';
    const impact = (valid.has(impactRaw) ? impactRaw : 'moderate') as AxeViolation['impact'];
    const rawTags = Array.isArray(entry['tags']) ? (entry['tags'] as unknown[]) : [];
    const tags = rawTags.filter((t): t is string => typeof t === 'string');
    const rawNodes = Array.isArray(entry['nodes']) ? (entry['nodes'] as unknown[]) : [];
    const nodes = rawNodes.map((n): AxeViolation['nodes'][number] => {
      if (typeof n !== 'object' || n === null) return { target: [], html: '', failureSummary: '' };
      const node = n as Record<string, unknown>;
      let target: string[] = [];
      const tgt = node['target'];
      if (typeof tgt === 'string') target = [tgt];
      else if (Array.isArray(tgt)) target = tgt.filter((x): x is string => typeof x === 'string');
      return {
        target,
        html: typeof node['html'] === 'string' ? node['html'] : '',
        failureSummary: typeof node['failureSummary'] === 'string' ? node['failureSummary'] : '',
      };
    });
    out.push({
      rule_id: ruleId,
      impact,
      help: typeof entry['help'] === 'string' ? entry['help'] : '',
      helpUrl: typeof entry['helpUrl'] === 'string' ? entry['helpUrl'] : '',
      description: typeof entry['description'] === 'string' ? entry['description'] : '',
      tags,
      nodes,
      experimental: tags.includes('experimental'),
    });
  }
  return out;
}
