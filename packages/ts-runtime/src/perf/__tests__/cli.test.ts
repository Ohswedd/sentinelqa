import { describe, expect, it } from 'vitest';

import { dispatchAsync } from '../../cli.js';
import type { auditPerf, AuditPerfLauncher } from '../audit.js';

const noopLauncher: AuditPerfLauncher = async () => ({
  newPage: async () => ({}) as never,
  close: async () => undefined,
});

describe('sentinel-ts audit-perf', () => {
  it('requires --input', async () => {
    const result = await dispatchAsync(['audit-perf']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('--input <path> is required');
  });

  it('passes through to the injected auditPerf function', async () => {
    let called: string | null = null;
    const stub: typeof auditPerf = async (opts) => {
      called = opts.inputPath;
      return {
        outcome: { pages: [], incomplete: false },
        indexPath: '/tmp/index.json',
      };
    };
    const result = await dispatchAsync(['audit-perf', '--input', '/tmp/x.json'], {
      auditPerfFn: stub,
      auditPerfLauncher: noopLauncher,
    });
    expect(called).toBe('/tmp/x.json');
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('/tmp/index.json');
  });

  it('surfaces audit errors as exit code 2', async () => {
    const stub: typeof auditPerf = async () => {
      throw new Error('Chromium launch failed');
    };
    const result = await dispatchAsync(['audit-perf', '--input', '/tmp/x.json'], {
      auditPerfFn: stub,
      auditPerfLauncher: noopLauncher,
    });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('Chromium launch failed');
  });

  it('USAGE lists audit-perf', async () => {
    const result = await dispatchAsync(['--help']);
    expect(result.stdout).toContain('audit-perf');
  });
});
