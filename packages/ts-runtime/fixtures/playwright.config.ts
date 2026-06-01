// Phase 04.07 — gated Playwright smoke config.
//
// Used only when SENTINELQA_HAS_CHROMIUM=1. Stands up the fixture
// sample-app via `webServer`, points the test runner at our custom
// reporter, and applies SENTINEL_PLAYWRIGHT_DEFAULTS so trace /
// screenshot / video evidence is always emitted on failure
// (see documentation).
//
// The reporter path and the helper import both point at `../dist/`
// (built artefacts). Node 24+'s strip-only TS loader doesn't accept
// some of our TS syntax (parameter properties); the smoke driver
// builds the package before invoking Playwright so `dist/` is fresh.

import { defineConfig } from '@playwright/test';

import { SENTINEL_PLAYWRIGHT_DEFAULTS } from '../dist/playwright.js';

export default defineConfig({
  testDir: './specs',
  workers: 1,
  retries: 0,
  reporter: [['../dist/reporter.js']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    ...SENTINEL_PLAYWRIGHT_DEFAULTS,
  },
  webServer: {
    // Playwright runs `command` from the config file's directory
    // (`packages/ts-runtime/fixtures/`), so `serve.mjs` is the bare
    // filename here — not `fixtures/serve.mjs`.
    command: 'node serve.mjs --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env['CI'],
    timeout: 30_000,
  },
});
