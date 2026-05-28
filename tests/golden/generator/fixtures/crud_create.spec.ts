// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Records" + ' — create', () => {
  test(
    'user can create a new ' + "record",
    { tag: ["@p1"] },
    async ({ page }) => {
      await page.goto("/records/new");

      await test.step('fill required fields', async () => {
        await page.getByLabel(/name/i).fill("Sentinel sample");
      });

      await test.step('submit form', async () => {
        await page.getByRole('button', { name: /create|save/i }).click();
      });

      await test.step('confirm creation outcome', async () => {
        await expect(page).toHaveURL(/records/i);
        await expect(page.getByText(/created/i)).toBeVisible();
      });
    },
  );

  test(
    'create rejects missing required fields',
    { tag: ["@p1"] },
    async ({ page }) => {
      await page.goto("/records/new");
      await page.getByRole('button', { name: /create|save/i }).click();
      await expect(page.getByText(/required/i)).toBeVisible();
    },
  );
});
