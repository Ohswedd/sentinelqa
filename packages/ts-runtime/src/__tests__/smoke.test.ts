import { describe, expect, it } from 'vitest';

import { dispatch, USAGE } from '../cli.js';
import { PACKAGE_NAME, VERSION } from '../version.js';

describe('ts-runtime smoke', () => {
  it('runs vitest under the strict tsconfig', () => {
    expect(1 + 1).toBe(2);
  });

  it('exports the package identity', async () => {
    const mod = await import('../index.js');
    expect(mod.PACKAGE_NAME).toBe('@sentinelqa/ts-runtime');
    expect(typeof mod.VERSION).toBe('string');
    expect(mod.VERSION).toMatch(/^\d+\.\d+\.\d+/);
  });

  it('renders --help on the CLI dispatcher', () => {
    const result = dispatch(['--help']);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toBe(USAGE);
    expect(result.stderr).toBe('');
  });

  it('renders --version on the CLI dispatcher', () => {
    const result = dispatch(['--version']);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toBe(`${PACKAGE_NAME} ${VERSION}\n`);
  });

  it('refuses unknown commands with exit 2', () => {
    const result = dispatch(['nope']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('unknown command');
  });

  it('marks Phase-04.03 commands as not-yet-implemented (exit 7)', () => {
    const result = dispatch(['run']);
    expect(result.exitCode).toBe(7);
    expect(result.stderr).toContain('lands in Phase 04.03');
  });
});
