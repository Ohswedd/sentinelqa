// Phase 04.07 — Chromium smoke. Gated behind SENTINELQA_HAS_CHROMIUM=1.
//
// This spec runs against the bundled fixture sample-app (served by
// `fixtures/serve.mjs`). The webServer config in
// `fixtures/playwright.config.ts` brings the server up before the
// test, and `--reporter=src/reporter.ts` routes events through our
// SentinelReporter so JSONL flows to stdout exactly as Python expects.
//
// Run locally:
//   pnpm --filter @sentinelqa/ts-runtime exec playwright install chromium
//   SENTINELQA_HAS_CHROMIUM=1 pnpm --filter @sentinelqa/ts-runtime exec \
//     playwright test --config fixtures/playwright.config.ts

import { expect, test } from '@playwright/test';

test('sample-app login flow', async ({ page }) => {
  await page.goto('/');

  await test.step('verify landing-page semantics', async () => {
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
  });

  await test.step('fill and submit', async () => {
    await page.getByLabel('Email').fill('alice@example.com');
    await page.getByRole('button', { name: /sign in/i }).click();
  });

  await test.step('confirm success page', async () => {
    await expect(page.getByRole('heading', { name: /welcome/i })).toBeVisible();
  });
});
