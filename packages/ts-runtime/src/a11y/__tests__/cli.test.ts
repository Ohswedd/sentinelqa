import { describe, it, expect } from 'vitest';

import { dispatchAsync } from '../../cli.js';
import type { auditA11y, AuditA11yLauncher } from '../audit.js';

const noopLauncher: AuditA11yLauncher = async () => ({
  newPage: async () => ({}) as never,
  close: async () => undefined,
});

describe('sentinel-ts audit-a11y', () => {
  it('requires --input', async () => {
    const result = await dispatchAsync(['audit-a11y']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('--input <path> is required');
  });

  it('passes through to the injected auditA11y function', async () => {
    let called: string | null = null;
    const stub: typeof auditA11y = async (opts) => {
      called = opts.inputPath;
      return {
        outcome: { pages: [], incomplete: false },
        indexPath: '/tmp/index.json',
      };
    };
    const result = await dispatchAsync(['audit-a11y', '--input', '/tmp/x.json'], {
      auditA11yFn: stub,
      auditA11yLauncher: noopLauncher,
    });
    expect(called).toBe('/tmp/x.json');
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('/tmp/index.json');
  });

  it('surfaces audit errors as exit code 2', async () => {
    const stub: typeof auditA11y = async () => {
      throw new Error('Chromium launch failed');
    };
    const result = await dispatchAsync(['audit-a11y', '--input', '/tmp/x.json'], {
      auditA11yFn: stub,
      auditA11yLauncher: noopLauncher,
    });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('Chromium launch failed');
  });
});
