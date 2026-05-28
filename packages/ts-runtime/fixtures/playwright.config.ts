// Phase 04.07 — gated Playwright smoke config.
//
// Used only when SENTINELQA_HAS_CHROMIUM=1. Stands up the fixture
// sample-app via `webServer`, points the test runner at our custom
// reporter, and applies SENTINEL_PLAYWRIGHT_DEFAULTS so trace /
// screenshot / video evidence is always emitted on failure
// (CLAUDE §21).

import { defineConfig } from '@playwright/test';

import { SENTINEL_PLAYWRIGHT_DEFAULTS } from '../src/playwright.js';

export default defineConfig({
  testDir: './specs',
  workers: 1,
  retries: 0,
  reporter: [['../src/reporter.ts']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    ...SENTINEL_PLAYWRIGHT_DEFAULTS,
  },
  webServer: {
    command: 'node fixtures/serve.mjs --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env['CI'],
    timeout: 30_000,
  },
});
