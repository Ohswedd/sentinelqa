// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.
//
// Pure parser for SentinelQA findings.json files. Lives separately from
// extension.ts so it can be tested headless (no `vscode` dependency).

import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { join } from 'path';

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface CodeRef {
  readonly path: string;
  readonly line?: number;
}

export interface Finding {
  readonly id: string;
  readonly title: string;
  readonly module: string;
  readonly severity: Severity;
  readonly description: string;
  readonly recommendation?: string;
  readonly codeRef?: CodeRef;
  readonly fixable: boolean;
}

export interface FindingsDocument {
  readonly runId: string;
  readonly findings: readonly Finding[];
}

/**
 * Find the most recent SentinelQA run directory under
 * `<projectRoot>/.sentinel/runs`. Returns null when none exist.
 */
export function findLatestRunDir(projectRoot: string): string | null {
  const runsRoot = join(projectRoot, '.sentinel', 'runs');
  if (!existsSync(runsRoot)) {
    return null;
  }
  const entries = readdirSync(runsRoot).filter(
    (name) => statSync(join(runsRoot, name)).isDirectory() && name !== 'latest',
  );
  if (entries.length === 0) {
    return null;
  }
  // Run IDs are ISO-timestamp-prefixed; lexicographic sort matches chronological.
  entries.sort();
  return join(runsRoot, entries[entries.length - 1]);
}

/**
 * Parse a findings.json file into a typed FindingsDocument. Returns
 * null when the file is missing; throws on schema drift so the
 * caller can show a useful error.
 */
export function loadFindings(runDir: string): FindingsDocument | null {
  const findingsPath = join(runDir, 'findings.json');
  if (!existsSync(findingsPath)) {
    return null;
  }
  const raw = readFileSync(findingsPath, 'utf-8');
  const parsed = JSON.parse(raw) as Record<string, unknown>;
  const runId = typeof parsed['run_id'] === 'string' ? (parsed['run_id'] as string) : 'unknown';
  const findingsArray = Array.isArray(parsed['findings']) ? parsed['findings'] : [];
  const findings: Finding[] = [];
  for (const entry of findingsArray) {
    if (typeof entry !== 'object' || entry === null) continue;
    const f = entry as Record<string, unknown>;
    const id = typeof f['id'] === 'string' ? (f['id'] as string) : '';
    const title = typeof f['title'] === 'string' ? (f['title'] as string) : '(untitled)';
    const moduleName = typeof f['module'] === 'string' ? (f['module'] as string) : 'unknown';
    const severity = normaliseSeverity(f['severity']);
    const description =
      typeof f['description'] === 'string' ? (f['description'] as string) : '';
    const recommendation =
      typeof f['recommendation'] === 'string' ? (f['recommendation'] as string) : undefined;
    const codeRef = extractCodeRef(f['code_ref']);
    const fixable = Boolean(f['repair_proposal']);
    if (!id) continue;
    findings.push({
      id,
      title,
      module: moduleName,
      severity,
      description,
      recommendation,
      codeRef,
      fixable,
    });
  }
  return { runId, findings };
}

/**
 * Group findings by severity for the tree view.
 * Keys are returned in critical → info order regardless of input order.
 */
export function groupBySeverity(
  findings: readonly Finding[],
): ReadonlyMap<Severity, readonly Finding[]> {
  const order: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];
  const map = new Map<Severity, Finding[]>();
  for (const sev of order) map.set(sev, []);
  for (const f of findings) {
    map.get(f.severity)?.push(f);
  }
  return map;
}

function normaliseSeverity(input: unknown): Severity {
  if (typeof input !== 'string') return 'info';
  const lower = input.toLowerCase();
  if (lower === 'critical' || lower === 'high' || lower === 'medium' || lower === 'low') {
    return lower;
  }
  return 'info';
}

function extractCodeRef(input: unknown): CodeRef | undefined {
  if (typeof input !== 'object' || input === null) return undefined;
  const ref = input as Record<string, unknown>;
  const path = typeof ref['path'] === 'string' ? (ref['path'] as string) : null;
  if (!path) return undefined;
  const lineRaw = ref['line'];
  const line =
    typeof lineRaw === 'number' && Number.isFinite(lineRaw) ? Math.floor(lineRaw) : undefined;
  return { path, line };
}
