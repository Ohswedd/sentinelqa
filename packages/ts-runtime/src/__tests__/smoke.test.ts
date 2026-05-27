import { describe, expect, it } from 'vitest';

describe('ts-runtime smoke', () => {
  it('runs vitest under the strict tsconfig', () => {
    expect(1 + 1).toBe(2);
  });

  it('imports the placeholder module without crashing', async () => {
    const mod = await import('../index.js');
    expect(mod).toBeDefined();
  });
});
