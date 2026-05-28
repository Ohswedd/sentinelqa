// `@sentinelqa/ts-runtime/playwright` — the surface SentinelQA-generated
// tests import (PRD §15.2, CLAUDE.md §21).
//
// Two pieces live here:
//
//   sentinelTest      — Playwright `test.extend` with auto fixtures:
//                       `sentinel`  → { emitter, testId, runDir }
//                       `_network`  → installs redactedNetwork on the page
//
//   SENTINEL_PLAYWRIGHT_DEFAULTS
//                     — the `use` block sentinel-ts merges into the
//                       Playwright config (trace, screenshot, video).
//                       CLAUDE §21: trace `on-first-retry`,
//                       screenshot `only-on-failure`,
//                       video `retain-on-failure`.
//
// Tests can call `sentinelStep(sentinel, name, fn)` and
// `captureEvidence(sentinel, page, label)` directly; the `sentinel`
// fixture exposes the right context shape.

import { test as baseTest } from '@playwright/test';
import type { PlaywrightWorkerOptions } from '@playwright/test';

import { redactedNetwork, type EvidenceContext, type StepContext } from './helpers.js';
import type { RoutablePage } from './helpers.js';
import { EventEmitter } from './protocol.js';

/**
 * Default `use` block for generated tests + sentinel-ts runs.
 * CLAUDE.md §21 — these defaults are mandatory.
 */
export const SENTINEL_PLAYWRIGHT_DEFAULTS = {
  trace: 'on-first-retry',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
} as const satisfies Partial<PlaywrightWorkerOptions>;

/**
 * Per-test SentinelQA context exposed as a Playwright fixture.
 */
export interface SentinelFixture extends EvidenceContext, StepContext {
  readonly emitter: EventEmitter;
  readonly runDir: string;
  readonly testId: string;
}

/**
 * Build a `SentinelFixture` from environment variables Playwright
 * inherits when launched by `sentinel-ts run`. Lands here so tests can
 * stub it: when the env vars are absent (e.g. authored test runs
 * outside sentinel-ts), we fall back to a no-op emitter writing to
 * stdout and a process-cwd runDir — generated tests still execute,
 * they just don't emit useful telemetry.
 */
export function buildSentinelFixture(
  testId: string,
  env: NodeJS.ProcessEnv = process.env,
): SentinelFixture {
  const runDir = env['SENTINELQA_RUN_DIR'] ?? process.cwd();
  return {
    emitter: new EventEmitter(),
    runDir,
    testId,
  };
}

/**
 * Playwright `test.extend` overlay. Generated tests import this:
 *
 *   import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';
 *
 * The `sentinel` fixture is the only auto-fixture: the network
 * interceptor is wired by reading `sentinel` so users don't pay the
 * cost on tests that don't need network telemetry. Tests opt in by
 * calling `redactedNetwork(page, sentinel)` themselves, or by including
 * `_network` in their test signature.
 */
export const sentinelTest = baseTest.extend<{
  sentinel: SentinelFixture;
  _network: void;
}>({
  // eslint-disable-next-line no-empty-pattern
  sentinel: async ({}, use, testInfo) => {
    const fixture = buildSentinelFixture(testInfo.testId);
    await use(fixture);
  },
  _network: [
    async ({ page, sentinel }, use) => {
      redactedNetwork(page as unknown as RoutablePage, sentinel);
      await use();
    },
    { auto: false },
  ],
});

export { expect } from '@playwright/test';
