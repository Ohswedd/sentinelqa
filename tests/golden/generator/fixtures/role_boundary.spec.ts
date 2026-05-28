// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Admin /admin" + ' — role boundary', () => {
  test(
    'anonymous request is redirected or denied',
    { tag: ["@p0", "@security"] },
    async ({ page }) => {
      const response = await page.goto("/admin");
      expect(
        response === null ||
          response.status() === 401 ||
          response.status() === 403 ||
          response.status() === 302 ||
          /login|sign[- ]?in/i.test(page.url()),
      ).toBeTruthy();
    },
  );

  test(
    'user without ' + "admin" + ' is blocked',
    { tag: ["@p0", "@security"] },
    async ({ page }) => {
      test.skip(
        process.env['SENTINEL_LOWPRIV_AUTH_STATE'] === undefined,
        'Lower-privilege storageState not provided; configure auth in sentinel.config.yaml.',
      );
      const response = await page.goto("/admin");
      expect(response?.status()).toBeGreaterThanOrEqual(400);
    },
  );
});
