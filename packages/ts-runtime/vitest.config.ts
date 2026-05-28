import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: [
      'src/**/*.{test,spec}.ts',
      'src/**/__tests__/**/*.{test,spec}.ts',
      'tests/**/*.{test,spec}.ts',
    ],
    environment: 'node',
    reporters: ['default'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/**/*.ts'],
      exclude: [
        'src/**/__tests__/**',
        'src/**/*.d.ts',
        'src/cli.ts',
        // playwright.ts's `test.extend(...)` is only exercisable by
        // actually running Playwright; the gated 04.07 smoke covers
        // it. The unit-testable parts (SENTINEL_PLAYWRIGHT_DEFAULTS,
        // buildSentinelFixture) live in playwright.test.ts but the
        // `test.extend(...)` IIFE body inflates the line count for no
        // unit-coverage signal.
        'src/playwright.ts',
      ],
      thresholds: {
        lines: 85,
        functions: 85,
        statements: 85,
        branches: 75,
      },
    },
  },
});
