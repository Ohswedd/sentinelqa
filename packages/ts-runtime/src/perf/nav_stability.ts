// Phase 12.05 — repeated-navigation stability collector.
//
// The orchestrator visits the same route N times (default 5). After each
// visit we read `performance.memory.usedJSHeapSize` (Chromium-only; null
// elsewhere) + the DOM-node count. The Python side computes the growth
// percentage between the first and last sample.
//
// CLAUDE §27: this is a heuristic, not Real-User Monitoring. Small growth
// is normal (caches warming). The Python finding text says so explicitly
// and downgrades confidence to 0.5.

import type { NavStabilitySample } from './types.js';

export function readNavSample(): {
  js_heap_bytes: number | null;
  dom_node_count: number;
} {
  const memory =
    performance &&
    (performance as unknown as { memory?: { usedJSHeapSize?: number } }).memory &&
    typeof (performance as unknown as { memory?: { usedJSHeapSize?: number } }).memory!
      .usedJSHeapSize === 'number'
      ? (performance as unknown as { memory: { usedJSHeapSize: number } }).memory.usedJSHeapSize
      : null;
  const domCount = document.getElementsByTagName('*').length;
  return { js_heap_bytes: memory, dom_node_count: domCount };
}

export interface RawNavSample {
  readonly js_heap_bytes: unknown;
  readonly dom_node_count: unknown;
}

export function normaliseNavSample(raw: RawNavSample): NavStabilitySample {
  const heap =
    typeof raw.js_heap_bytes === 'number' && Number.isFinite(raw.js_heap_bytes)
      ? raw.js_heap_bytes
      : null;
  const dom =
    typeof raw.dom_node_count === 'number' && Number.isFinite(raw.dom_node_count)
      ? Math.max(0, Math.floor(raw.dom_node_count))
      : null;
  return {
    js_heap_bytes: heap,
    dom_node_count: dom,
  };
}
