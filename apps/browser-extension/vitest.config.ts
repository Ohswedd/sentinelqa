// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // recorder.test.ts requires a DOM; loopback.test.ts is happy in node
    // but tolerates jsdom. Pick jsdom so both work.
    environment: 'jsdom',
    passWithNoTests: true,
  },
});
