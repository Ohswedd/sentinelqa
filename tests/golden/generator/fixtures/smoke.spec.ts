// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Smoke /login", () => {
  test(
    "smoke /login",
    { tag: ["@p0", "@critical"] },
    async ({ page }) => {
      await page.goto("/login");

      await test.step('verify page url', async () => {
        await expect(page).toHaveURL(/\/login/i);
      });

      await test.step('assert stable anchor element', async () => {
        await expect(
          page.getByRole("heading", { name: /sign in/i }),
        ).toBeVisible();
      });
    },
  );
});
