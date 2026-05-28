// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Records" + ' — delete', () => {
  test(
    'user can delete a ' + "record",
    { tag: ["@p1"] },
    async ({ page }) => {
      await page.goto("/records/123");

      await test.step('initiate delete', async () => {
        await page.getByRole('button', { name: /delete|remove/i }).click();
      });

      await test.step('confirm in dialog', async () => {
        await page.getByRole('button', { name: /confirm|yes/i }).click();
      });

      await test.step('confirm deletion outcome', async () => {
        await expect(page).toHaveURL(/records/i);
        await expect(page.getByText(/deleted/i)).toBeVisible();
      });
    },
  );
});
