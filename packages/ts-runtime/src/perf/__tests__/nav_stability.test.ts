import { afterEach, describe, expect, it } from 'vitest';

import { normaliseNavSample, readNavSample } from '../nav_stability.js';

describe('normaliseNavSample', () => {
  it('preserves valid heap + dom counts', () => {
    expect(normaliseNavSample({ js_heap_bytes: 12345, dom_node_count: 678 })).toEqual({
      js_heap_bytes: 12345,
      dom_node_count: 678,
    });
  });
  it('floors floats for dom node count', () => {
    expect(normaliseNavSample({ js_heap_bytes: 1, dom_node_count: 12.7 })).toEqual({
      js_heap_bytes: 1,
      dom_node_count: 12,
    });
  });
  it('clamps negative dom node count to zero', () => {
    expect(normaliseNavSample({ js_heap_bytes: 1, dom_node_count: -3 })).toEqual({
      js_heap_bytes: 1,
      dom_node_count: 0,
    });
  });
  it('treats missing fields as null', () => {
    expect(normaliseNavSample({ js_heap_bytes: undefined, dom_node_count: undefined })).toEqual({
      js_heap_bytes: null,
      dom_node_count: null,
    });
  });
  it('rejects non-finite numbers', () => {
    expect(
      normaliseNavSample({ js_heap_bytes: Number.NaN, dom_node_count: Number.POSITIVE_INFINITY }),
    ).toEqual({ js_heap_bytes: null, dom_node_count: null });
  });
});

describe('readNavSample', () => {
  let originalDoc: unknown;
  let originalPerf: unknown;

  afterEach(() => {
    (globalThis as { document?: unknown }).document = originalDoc;
    (globalThis as { performance?: unknown }).performance = originalPerf;
  });

  it('returns memory + dom count when both are available', () => {
    originalDoc = (globalThis as { document?: unknown }).document;
    originalPerf = (globalThis as { performance?: unknown }).performance;
    (globalThis as { performance: unknown }).performance = {
      memory: { usedJSHeapSize: 524_288 },
      getEntriesByType: () => [],
    };
    (globalThis as { document: unknown }).document = {
      getElementsByTagName: () => ({ length: 123 }),
    };
    const sample = readNavSample();
    expect(sample.js_heap_bytes).toBe(524_288);
    expect(sample.dom_node_count).toBe(123);
  });

  it('returns null heap when performance.memory missing', () => {
    originalDoc = (globalThis as { document?: unknown }).document;
    originalPerf = (globalThis as { performance?: unknown }).performance;
    (globalThis as { performance: unknown }).performance = {
      getEntriesByType: () => [],
    };
    (globalThis as { document: unknown }).document = {
      getElementsByTagName: () => ({ length: 5 }),
    };
    const sample = readNavSample();
    expect(sample.js_heap_bytes).toBe(null);
    expect(sample.dom_node_count).toBe(5);
  });
});
