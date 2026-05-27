import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.{test,spec}.ts', 'src/**/__tests__/**/*.{test,spec}.ts'],
    environment: 'node',
    reporters: ['default'],
  },
});
