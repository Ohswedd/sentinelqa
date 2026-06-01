// — orchestrates the per-route accessibility audit and writes
// the JSON artifacts (`<run-dir>/a11y/<route-slug>.json` + `index.json`)
// the Python module reads.
// The orchestrator accepts an injectable `launcher` and `pageVisitor`
// so the CLI subcommand can wire in Playwright in production while
// tests substitute a deterministic stub.

import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve as resolvePath } from 'node:path';

import { normaliseViolations, runAxe, type RawAxeRunResult } from './axe.js';
import { walkFocus, type KeyboardWalkResult } from './keyboard.js';
import { detectLandmarkIssues, readLandmarkCounts, type LandmarkCounts } from './landmarks.js';
import {
  detectMissingAccessibleNames,
  readInteractiveSamples,
  type ElementSample,
} from './sr_names.js';
import {
  A11Y_RESULT_SCHEMA_VERSION,
  type A11yPageResult,
  type A11yRunOutcome,
  type AxeViolation,
  type KeyboardIssue,
  type LandmarkIssue,
  type AccessibleNameIssue,
} from './types.js';

export interface AuditA11yRunConfig {
  readonly schema_version: string;
  readonly run_id: string;
  readonly target: string;
  readonly out_dir: string;
  readonly routes: readonly string[];
  readonly axe_tags: readonly string[];
  readonly request_timeout_ms: number;
  readonly keyboard_max_tabs: number;
}

export interface AuditA11yPage {
  goto(url: string, opts?: { timeout?: number }): Promise<unknown>;
  url(): string;
  addScriptTag(opts: { content: string }): Promise<unknown>;
  evaluate<T>(fn: (...args: never[]) => T | Promise<T>, ...args: never[]): Promise<T>;
  keyboard: { press(key: string): Promise<void> };
}

export interface AuditA11yBrowser {
  newPage(): Promise<AuditA11yPage>;
  close(): Promise<void>;
}

export type AuditA11yLauncher = () => Promise<AuditA11yBrowser>;

export interface AuditA11yOptions {
  readonly inputPath: string;
  readonly launcher: AuditA11yLauncher;
  readonly axeSource?: string;
  readonly now?: () => Date;
}

export interface AuditA11yResult {
  readonly outcome: A11yRunOutcome;
  readonly indexPath: string;
}

const VALID_KEYBOARD: ReadonlySet<string> = new Set([
  'keyboard-navigation',
  'focus-trap',
  'focus-visible',
]);

export function loadRunConfig(raw: unknown): AuditA11yRunConfig {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    throw new Error('audit-a11y run-config must be a JSON object.');
  }
  const obj = raw as Record<string, unknown>;
  const requireString = (key: string): string => {
    const v = obj[key];
    if (typeof v !== 'string' || v.length === 0) {
      throw new Error(`audit-a11y run-config: '${key}' must be a non-empty string.`);
    }
    return v;
  };
  const requireStringArray = (key: string): readonly string[] => {
    const v = obj[key];
    if (!Array.isArray(v)) {
      throw new Error(`audit-a11y run-config: '${key}' must be a string array.`);
    }
    const arr = v.filter((x): x is string => typeof x === 'string');
    if (arr.length === 0) {
      throw new Error(`audit-a11y run-config: '${key}' must contain at least one entry.`);
    }
    return arr;
  };
  const requireInt = (key: string): number => {
    const v = obj[key];
    if (typeof v !== 'number' || !Number.isInteger(v) || v <= 0) {
      throw new Error(`audit-a11y run-config: '${key}' must be a positive integer.`);
    }
    return v;
  };
  return {
    schema_version: typeof obj['schema_version'] === 'string' ? obj['schema_version'] : '1',
    run_id: requireString('run_id'),
    target: requireString('target'),
    out_dir: requireString('out_dir'),
    routes: requireStringArray('routes'),
    axe_tags: requireStringArray('axe_tags'),
    request_timeout_ms: requireInt('request_timeout_ms'),
    keyboard_max_tabs: requireInt('keyboard_max_tabs'),
  };
}

export function routeSlug(route: string): string {
  if (route === '' || route === '/') return 'root';
  const cleaned = route.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  return cleaned.length === 0 ? 'root' : cleaned;
}

function urlFor(target: string, route: string): string {
  if (route.startsWith('http://') || route.startsWith('https://')) return route;
  const stripped = target.endsWith('/') ? target.slice(0, -1) : target;
  const path = route.startsWith('/') ? route : '/' + route;
  return stripped + path;
}

export async function auditA11y(opts: AuditA11yOptions): Promise<AuditA11yResult> {
  if (!existsSync(opts.inputPath)) {
    throw new Error(`audit-a11y: input path not found: ${opts.inputPath}`);
  }
  const raw = await readFile(opts.inputPath, 'utf-8');
  const cfg = loadRunConfig(JSON.parse(raw));
  await mkdir(cfg.out_dir, { recursive: true });

  const now = opts.now ?? (() => new Date());
  const browser = await opts.launcher();
  const pages: A11yPageResult[] = [];
  let incomplete = false;

  try {
    for (const route of cfg.routes) {
      const page = await browser.newPage();
      const url = urlFor(cfg.target, route);
      const started = Date.now();
      let pageError: string | null = null;
      let axe: RawAxeRunResult = { violations: [] };
      let keyboard: KeyboardWalkResult = { samples: [], issues: [] };
      let landmarks: LandmarkCounts = { main: 0, header: 0, nav: 0, footer: 0 };
      let samples: readonly ElementSample[] = [];
      try {
        await page.goto(url, { timeout: cfg.request_timeout_ms });
        axe = await runAxe(page as never, {
          tags: cfg.axe_tags,
          ...(opts.axeSource !== undefined ? { axeSourceOverride: opts.axeSource } : {}),
        });
        landmarks = await readLandmarkCounts(page as never);
        samples = await readInteractiveSamples(page as never);
        keyboard = await walkFocus(page as never, { max: cfg.keyboard_max_tabs });
      } catch (err) {
        pageError = (err as Error).message;
        incomplete = true;
      }

      const axeViolations: AxeViolation[] = normaliseViolations(axe.violations);
      const keyboardIssues: KeyboardIssue[] = keyboard.issues
        .filter((issue) => VALID_KEYBOARD.has(issue.category))
        .slice();
      const landmarkIssues: LandmarkIssue[] = detectLandmarkIssues(landmarks);
      const accessibleNameIssues: AccessibleNameIssue[] = detectMissingAccessibleNames(samples);

      const result: A11yPageResult = {
        route,
        url,
        fetched_at: now().toISOString(),
        axe_violations: axeViolations,
        keyboard_issues: keyboardIssues,
        landmark_issues: landmarkIssues,
        accessible_name_issues: accessibleNameIssues,
        duration_ms: Date.now() - started,
        schema_version: A11Y_RESULT_SCHEMA_VERSION,
        error: pageError,
      };
      pages.push(result);
      const perRoutePath = resolvePath(cfg.out_dir, `${routeSlug(route)}.json`);
      await writeFile(perRoutePath, JSON.stringify(result, null, 2) + '\n', 'utf-8');
    }
  } finally {
    await browser.close();
  }

  const outcome: A11yRunOutcome = { pages, incomplete };
  const indexPath = resolvePath(cfg.out_dir, 'index.json');
  await writeFile(indexPath, JSON.stringify(outcome, null, 2) + '\n', 'utf-8');
  return { outcome, indexPath };
}
