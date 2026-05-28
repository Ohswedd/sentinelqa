// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe('Authentication — logout', () => {
  test(
    'authenticated user can log out',
    { tag: ["@p1"] },
    async ({ page }) => {
      test.skip(
        process.env['SENTINEL_AUTH_STATE'] === undefined,
        'Authenticated session not available; run `sentinel generate` with auth config to enable.',
      );
      await page.goto("/dashboard");

      await test.step('open logout control', async () => {
        await page.getByRole('button', { name: /log out|sign out/i }).click();
      });

      await test.step('confirm logout outcome', async () => {
        await expect(page).toHaveURL(/login|home/i);
        await expect(page.getByText(/logged out/i)).toBeVisible();
      });
    },
  );
});
