// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

const SANDBOX_CARD = {
  number: "4242 4242 4242 4242",
  exp: "12 / 34",
  cvc: "123",
} as const;

test.describe('Payment sandbox', () => {
  test(
    'user can complete a sandbox checkout',
    { tag: ["@p0", "@payment"] },
    async ({ page }) => {
      test.skip(
        process.env['SENTINEL_PAYMENT_SANDBOX'] !== '1',
        'Set SENTINEL_PAYMENT_SANDBOX=1 to exercise payment flows against the sandbox.',
      );
      await page.goto("/checkout");

      await test.step('fill sandbox card', async () => {
        await page.getByLabel(/card number/i).fill(SANDBOX_CARD.number);
        await page.getByLabel(/expiration/i).fill(SANDBOX_CARD.exp);
        await page.getByLabel(/cvc/i).fill(SANDBOX_CARD.cvc);
      });

      await test.step('submit and confirm', async () => {
        await page.getByRole('button', { name: /pay|complete order/i }).click();
        await expect(page.getByText(/thank you/i)).toBeVisible();
      });
    },
  );
});
