// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Records" + ' — list & read', () => {
  test(
    'list page renders ' + "records",
    { tag: ["@p2"] },
    async ({ page }) => {
      await page.goto("/records");

      await test.step('assert list landmark', async () => {
        await expect(
          page.getByRole("list", { name: /records/i }),
        ).toBeVisible();
      });
    },
  );

  test(
    'detail page renders for an existing ' + "record",
    { tag: ["@p2"] },
    async ({ page }) => {
      await page.goto("/records/123");
      await expect(page).toHaveURL(/\/records\/123/i);
      await expect(page.getByRole('main')).toBeVisible();
    },
  );
});
