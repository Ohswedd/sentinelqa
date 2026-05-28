// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Records" + ' — update', () => {
  test(
    'user can update an existing ' + "record",
    { tag: ["@p1"] },
    async ({ page }) => {
      await page.goto("/records/123/edit");

      await test.step('change a field', async () => {
        const field = page.getByLabel(/name/i);
        await field.fill('');
        await field.fill("updated");
      });

      await test.step('save', async () => {
        await page.getByRole('button', { name: /save|update/i }).click();
      });

      await test.step('confirm update outcome', async () => {
        await expect(page).toHaveURL(/records/i);
        await expect(page.getByText(/saved/i)).toBeVisible();
      });
    },
  );
});
