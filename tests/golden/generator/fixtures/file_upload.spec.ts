// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';
import { Buffer } from 'node:buffer';

const FIXTURE_FILE = {
  name: "sentinel-fixture.txt",
  mimeType: "text/plain",
  // Tiny in-memory payload so the test does not depend on the filesystem.
  buffer: Buffer.from("U2VudGluZWxRQQ==", 'base64'),
} as const;

test.describe('File upload', () => {
  test(
    'user can upload a small ' + "text" + ' file',
    { tag: ["@p2"] },
    async ({ page }) => {
      await page.goto("/upload");

      await test.step('attach file', async () => {
        const input = page.getByLabel(/upload/i);
        await input.setInputFiles({
          name: FIXTURE_FILE.name,
          mimeType: FIXTURE_FILE.mimeType,
          buffer: FIXTURE_FILE.buffer,
        });
      });

      await test.step('submit', async () => {
        await page.getByRole('button', { name: /upload/i }).click();
      });

      await test.step('confirm upload outcome', async () => {
        await expect(page.getByText(/uploaded/i)).toBeVisible();
      });
    },
  );
});
