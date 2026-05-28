// Tests for `auditLocators` (runner.ts) + the sentinel-ts CLI subcommand
// added in Phase 07 task 04.

import { describe, expect, it } from 'vitest';

import { dispatchAsync } from '../cli.js';
import { auditLocators } from '../runner.js';

describe('auditLocators (programmatic)', () => {
  it('returns a clean report for a semantic-only spec', async () => {
    const report = await auditLocators({
      files: ['ok.ts'],
      cwd: '/tmp/audit-doesnt-matter',
      readFileFn: async () =>
        "import { test } from '@playwright/test';\n" +
        "test('x', async ({ page }) => { await page.getByRole('button').click(); });\n",
    });
    expect(report.schema_version).toBe('1.0.0');
    expect(report.files_scanned).toBe(1);
    expect(report.findings).toEqual([]);
  });

  it('reports brittle CSS findings', async () => {
    const report = await auditLocators({
      files: ['brittle.ts'],
      cwd: '/tmp/audit-doesnt-matter',
      readFileFn: async () =>
        "import { test } from '@playwright/test';\n" +
        "test('x', async ({ page }) => {\n" +
        "  await page.locator('div:nth-of-type(3)').click();\n" +
        '});\n',
    });
    expect(report.findings.length).toBeGreaterThan(0);
    expect(report.findings[0]?.file).toBe('brittle.ts');
  });

  it('sorts findings by (file, line, column)', async () => {
    const report = await auditLocators({
      files: ['a.ts', 'b.ts'],
      cwd: '/tmp/audit-doesnt-matter',
      readFileFn: async (p: string) =>
        p.endsWith('a.ts')
          ? "import { test } from '@playwright/test';\ntest('x', async ({ page }) => { await page.locator('//div').click(); });\n"
          : "import { test } from '@playwright/test';\ntest('y', async ({ page }) => { await page.locator(':nth-child(2)').click(); });\n",
    });
    expect(report.findings.length).toBeGreaterThan(0);
    const files = report.findings.map((f) => f.file);
    const sorted = [...files].sort();
    expect(files).toEqual(sorted);
  });

  it('honors an injected auditFn (used for unit-test mocking)', async () => {
    const report = await auditLocators({
      files: ['x.ts'],
      cwd: '/tmp',
      readFileFn: async () => 'irrelevant',
      auditFn: () => ({
        warnings: [{ line: 1, column: 1, message: 'mock', snippet: '' }],
      }),
    });
    expect(report.findings).toEqual([
      { file: 'x.ts', line: 1, column: 1, message: 'mock', snippet: '' },
    ]);
  });
});

describe('sentinel-ts audit-locators CLI', () => {
  it('exits 0 with empty findings on clean specs', async () => {
    const result = await dispatchAsync(['audit-locators', '--file', 'ok.ts'], {
      auditLocatorsFn: async () => ({
        schema_version: '1.0.0' as const,
        files_scanned: 1,
        findings: [],
      }),
    });
    expect(result.exitCode).toBe(0);
    expect(JSON.parse(result.stdout.trim()).findings).toEqual([]);
  });

  it('exits 1 when findings are returned', async () => {
    const result = await dispatchAsync(['audit-locators', '--file', 'bad.ts'], {
      auditLocatorsFn: async () => ({
        schema_version: '1.0.0' as const,
        files_scanned: 1,
        findings: [{ file: 'bad.ts', line: 1, column: 1, message: 'brittle', snippet: '' }],
      }),
    });
    expect(result.exitCode).toBe(1);
  });

  it('rejects an invocation without --file', async () => {
    const result = await dispatchAsync(['audit-locators']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('--file');
  });

  it('exits 2 when the audit subprocess throws', async () => {
    const result = await dispatchAsync(['audit-locators', '--file', 'x.ts'], {
      auditLocatorsFn: async () => {
        throw new Error('audit blew up');
      },
    });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('audit blew up');
  });

  it('lists audit-locators in --help output', async () => {
    const help = await dispatchAsync(['--help']);
    expect(help.stdout).toContain('audit-locators');
  });
});
