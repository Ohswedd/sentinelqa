// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { findLatestRunDir, groupBySeverity, loadFindings } from './findings';

let workspace: string;

beforeEach(() => {
  workspace = mkdtempSync(join(tmpdir(), 'sentinelqa-vsx-'));
});

afterEach(() => {
  rmSync(workspace, { recursive: true, force: true });
});

describe('findLatestRunDir', () => {
  it('returns null when .sentinel/runs is missing', () => {
    expect(findLatestRunDir(workspace)).toBeNull();
  });

  it('returns the lexicographically-latest run directory', () => {
    const runsRoot = join(workspace, '.sentinel', 'runs');
    mkdirSync(join(runsRoot, '2026-01-01T00-00-00Z-a'), { recursive: true });
    mkdirSync(join(runsRoot, '2026-06-01T12-00-00Z-b'), { recursive: true });
    mkdirSync(join(runsRoot, '2026-03-15T08-00-00Z-c'), { recursive: true });
    const latest = findLatestRunDir(workspace);
    expect(latest).not.toBeNull();
    expect(latest?.endsWith('2026-06-01T12-00-00Z-b')).toBe(true);
  });

  it('skips a "latest" symlink-style directory entry', () => {
    const runsRoot = join(workspace, '.sentinel', 'runs');
    mkdirSync(join(runsRoot, '2026-01-01T00-00-00Z-a'), { recursive: true });
    mkdirSync(join(runsRoot, 'latest'), { recursive: true });
    const latest = findLatestRunDir(workspace);
    expect(latest?.endsWith('2026-01-01T00-00-00Z-a')).toBe(true);
  });
});

describe('loadFindings', () => {
  it('returns null when findings.json is missing', () => {
    const runDir = join(workspace, 'run-1');
    mkdirSync(runDir, { recursive: true });
    expect(loadFindings(runDir)).toBeNull();
  });

  it('parses a well-formed findings.json', () => {
    const runDir = join(workspace, 'run-1');
    mkdirSync(runDir, { recursive: true });
    writeFileSync(
      join(runDir, 'findings.json'),
      JSON.stringify({
        run_id: 'run-1',
        findings: [
          {
            id: 'F-1',
            title: 'Missing Content-Security-Policy header',
            module: 'security',
            severity: 'high',
            description: 'No CSP header on /',
            recommendation: 'Add a strict CSP.',
            code_ref: { path: 'app/server.ts', line: 42 },
          },
          {
            id: 'F-2',
            title: 'Hardcoded credential in bundle',
            module: 'security',
            severity: 'critical',
            description: 'sk_live_… leaked in main.js',
            repair_proposal: { kind: 'patch' },
          },
        ],
      }),
    );
    const doc = loadFindings(runDir);
    expect(doc).not.toBeNull();
    expect(doc?.runId).toBe('run-1');
    expect(doc?.findings.length).toBe(2);
    expect(doc?.findings[0].codeRef).toEqual({ path: 'app/server.ts', line: 42 });
    expect(doc?.findings[1].fixable).toBe(true);
  });

  it('falls back to info severity for unknown values', () => {
    const runDir = join(workspace, 'run-1');
    mkdirSync(runDir, { recursive: true });
    writeFileSync(
      join(runDir, 'findings.json'),
      JSON.stringify({
        run_id: 'run-1',
        findings: [{ id: 'F-1', title: 'X', module: 'mod', severity: 'EXTREME' }],
      }),
    );
    const doc = loadFindings(runDir);
    expect(doc?.findings[0].severity).toBe('info');
  });
});

describe('groupBySeverity', () => {
  it('returns groups in the canonical severity order', () => {
    const findings = [
      { id: '1', title: 't', module: 'm', severity: 'low' as const, description: '', fixable: false },
      { id: '2', title: 't', module: 'm', severity: 'critical' as const, description: '', fixable: false },
      { id: '3', title: 't', module: 'm', severity: 'medium' as const, description: '', fixable: false },
    ];
    const groups = groupBySeverity(findings);
    const order = Array.from(groups.keys());
    expect(order).toEqual(['critical', 'high', 'medium', 'low', 'info']);
    expect(groups.get('critical')?.length).toBe(1);
    expect(groups.get('high')?.length).toBe(0);
    expect(groups.get('medium')?.length).toBe(1);
    expect(groups.get('low')?.length).toBe(1);
  });
});
