// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

const EMAIL_ENV = "SENTINEL_EMAIL";
const PASSWORD_ENV = "SENTINEL_PASSWORD";

function readCredential(envName: string): string | null {
  const value = process.env[envName];
  return value && value.length > 0 ? value : null;
}

test.describe('Authentication — login', () => {
  test(
    'user can log in with valid credentials',
    { tag: ["@p0", "@auth"] },
    async ({ page }) => {
      const email = readCredential(EMAIL_ENV);
      const password = readCredential(PASSWORD_ENV);
      test.skip(
        email === null || password === null,
        `Set ${EMAIL_ENV} and ${PASSWORD_ENV} to run the authenticated login flow.`,
      );

      await page.goto("/login");

      await test.step('fill credentials and submit', async () => {
        await page.getByLabel(/email/i).fill(email as string);
        await page.getByLabel(/password/i).fill(password as string);
        await page.getByRole('button', { name: /sign in|log in/i }).click();
      });

      await test.step('confirm post-login surface', async () => {
        await expect(page).toHaveURL(/dashboard|home/i);
        await expect(page.getByRole("navigation")).toBeVisible();
      });
    },
  );

  test(
    'login form shows validation when credentials are missing',
    { tag: ["@p0", "@auth"] },
    async ({ page }) => {
      await page.goto("/login");

      await test.step('submit empty form', async () => {
        await page.getByRole('button', { name: /sign in|log in/i }).click();
      });

      await test.step('error surface is visible', async () => {
        await expect(
          page.getByText(/required|invalid/i),
        ).toBeVisible();
      });
    },
  );
});
