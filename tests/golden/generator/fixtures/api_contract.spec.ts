// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("GET /api/users" + ' — contract', () => {
  test(
    "GET" + ' ' + "/api/users" + ' returns the documented status',
    { tag: ["@p1", "@api"] },
    async ({ request }) => {
      const response = await request.fetch("/api/users", {
        method: "GET",
      });

      await test.step('status code is in the documented set', async () => {
        const expected = [200];
        expect(expected).toContain(response.status());
      });

      await test.step('content-type matches the contract', async () => {
        const contentType = response.headers()['content-type'] ?? '';
        expect(contentType.toLowerCase()).toContain("json");
      });
    },
  );

  test(
    "GET" + ' ' + "/api/users" + ' rejects unauthenticated request',
    { tag: ["@p1", "@api"] },
    async ({ request }) => {
      test.skip(true, 'Endpoint allows anonymous access.');
      const response = await request.fetch("/api/users", {
        method: "GET",
      });
      expect([401, 403]).toContain(response.status());
    },
  );
});
