// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

const SAMPLE_DATA = {
  email: "sentinel+signup@example.com",
  password: "S3ntinel-Sample!",
} as const;

test.describe('Authentication — signup', () => {
  test(
    'new user can sign up',
    { tag: ["@p0"] },
    async ({ page }) => {
      await page.goto("/signup");

      await test.step('fill signup form', async () => {
        await page.getByLabel(/email/i).fill(SAMPLE_DATA.email);
        await page.getByLabel(/password/i).fill(SAMPLE_DATA.password);
        await page
          .getByLabel(/confirm password/i)
          .fill(SAMPLE_DATA.password);
        await page.getByRole('button', { name: /create account|sign up/i }).click();
      });

      await test.step('confirm signup outcome', async () => {
        await expect(page).toHaveURL(/welcome|onboarding/i);
      });
    },
  );

  test(
    'signup rejects an obviously invalid email',
    { tag: ["@p0"] },
    async ({ page }) => {
      await page.goto("/signup");
      await page.getByLabel(/email/i).fill('not-an-email');
      await page.getByRole('button', { name: /create account|sign up/i }).click();
      await expect(page.getByText(/valid email/i)).toBeVisible();
    },
  );
});
