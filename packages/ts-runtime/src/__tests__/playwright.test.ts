import { describe, expect, it } from 'vitest';

import { buildSentinelFixture, SENTINEL_PLAYWRIGHT_DEFAULTS, sentinelTest } from '../playwright.js';

describe('SENTINEL_PLAYWRIGHT_DEFAULTS', () => {
  it('matches CLAUDE §21 defaults', () => {
    expect(SENTINEL_PLAYWRIGHT_DEFAULTS).toStrictEqual({
      trace: 'on-first-retry',
      screenshot: 'only-on-failure',
      video: 'retain-on-failure',
    });
  });
});

describe('buildSentinelFixture', () => {
  it('reads SENTINELQA_RUN_DIR from env when present', () => {
    const fixture = buildSentinelFixture('t-1', { SENTINELQA_RUN_DIR: '/tmp/runs/x' });
    expect(fixture.testId).toBe('t-1');
    expect(fixture.runDir).toBe('/tmp/runs/x');
    expect(fixture.emitter).toBeDefined();
  });

  it('falls back to process.cwd() when env var is absent', () => {
    const fixture = buildSentinelFixture('t-2', {});
    expect(fixture.runDir).toBe(process.cwd());
  });
});

describe('sentinelTest export', () => {
  it('is callable as a Playwright test.extend result', () => {
    // We can't actually run a Playwright test inside vitest, but we
    // can prove the extended test exists and has the expected shape.
    expect(typeof sentinelTest).toBe('function');
    // `.extend` chained on the result should also be a function (we
    // re-exported Playwright's test.extend).
    expect(typeof (sentinelTest as unknown as { extend: unknown }).extend).toBe('function');
  });
});
