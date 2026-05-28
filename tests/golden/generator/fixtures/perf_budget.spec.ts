// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

const BUDGETS = {
  loadMs: 3000,
  bytes: 1500000,
} as const;

test.describe("Home" + ' — performance budget', () => {
  test(
    'page loads within budget',
    { tag: ["@p2", "@perf"] },
    async ({ page }) => {
      const started = Date.now();
      const response = await page.goto("/", { waitUntil: 'load' });
      const elapsed = Date.now() - started;

      await test.step('document load time within budget', async () => {
        expect(elapsed).toBeLessThanOrEqual(BUDGETS.loadMs);
      });

      await test.step('document byte size within budget', async () => {
        const body = await response?.body();
        expect((body?.length ?? 0)).toBeLessThanOrEqual(BUDGETS.bytes);
      });
    },
  );
});
