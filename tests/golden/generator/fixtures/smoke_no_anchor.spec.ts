// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Smoke /", () => {
  test(
    "smoke /",
    { tag: ["@p3"] },
    async ({ page }) => {
      await page.goto("/");

      await test.step('verify page url', async () => {
        await expect(page).toHaveURL(/\//i);
      });

      await test.step('assert at least one landmark is present', async () => {
        await expect(page.getByRole('main').or(page.getByRole('navigation')).first()).toBeVisible();
      });
    },
  );
});
