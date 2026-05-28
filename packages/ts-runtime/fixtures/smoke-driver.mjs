#!/usr/bin/env node
// Phase 04.07 — gated Playwright smoke driver.
//
// Runs `playwright test --config=fixtures/playwright.config.ts` ONLY
// when SENTINELQA_HAS_CHROMIUM=1. The CI smoke lane sets this; default
// `pnpm test` does not, so contributors without Chromium installed
// don't get surprised.
//
// Exit codes mirror Playwright's: 0 = pass, 1 = at least one test
// failed, ≥2 = framework error.

import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const pkgRoot = resolve(here, '..');

if (process.env.SENTINELQA_HAS_CHROMIUM !== '1') {
  console.log(
    'sentinel-ts: SENTINELQA_HAS_CHROMIUM != 1, skipping Playwright smoke. ' +
      'Set SENTINELQA_HAS_CHROMIUM=1 to enable.',
  );
  process.exit(0);
}

const child = spawn(
  'npx',
  ['playwright', 'test', '--config=fixtures/playwright.config.ts', ...process.argv.slice(2)],
  {
    cwd: pkgRoot,
    stdio: 'inherit',
    env: process.env,
  },
);

child.on('error', (err) => {
  console.error(`smoke-driver: failed to spawn playwright: ${err.message}`);
  process.exit(2);
});

child.on('close', (code) => {
  process.exit(code ?? 1);
});
