// SentinelQA Generated — do not edit by hand.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).

import { sentinelTest as test, expect } from '@sentinelqa/ts-runtime/playwright';

test.describe("Smoke /" + ' — automated accessibility checks', () => {
  test(
    'axe-core finds no critical or serious violations',
    { tag: ["@p2", "@a11y"] },
    async ({ page }) => {
      // axe-core is loaded by the runner (Phase 11). The fallback below
      // skips the assertion gracefully so the spec compiles and runs
      // outside the full SentinelQA pipeline.
      await page.goto("/");

      const axe = (globalThis as { __SENTINEL_AXE__?: { run: (page: unknown) => Promise<{ violations: { impact?: string }[] }> } }).__SENTINEL_AXE__;
      test.skip(axe === undefined, 'axe-core runtime not bound — wired in by Phase 11.');

      const result = await axe!.run(page);
      const blocking = result.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious');
      expect(blocking).toEqual([]);
    },
  );
});
