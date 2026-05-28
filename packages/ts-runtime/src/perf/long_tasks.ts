// Phase 12.04 — long-task collector via PerformanceObserver.
//
// PerformanceObserver({ entryTypes: ['longtask'] }) reports any main-thread
// task longer than 50ms. We install the observer before navigation and
// summarise after the load completes. CLAUDE §27: this is a synthetic
// lab measurement, not Real-User Monitoring.

import type { LongTaskSummary } from './types.js';

interface LongTaskWindow {
  __sentinelLongTasks?: { entries: { duration: number; startTime: number }[] };
}

export function prepLongTaskObserver(): void {
  const w = window as unknown as LongTaskWindow;
  if (!w.__sentinelLongTasks) {
    w.__sentinelLongTasks = { entries: [] };
  }
  try {
    const obs = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        w.__sentinelLongTasks!.entries.push({
          duration: entry.duration ?? 0,
          startTime: entry.startTime ?? 0,
        });
      }
    });
    obs.observe({ type: 'longtask', buffered: true });
  } catch {
    /* longtask not supported in this browser */
  }
}

export function readLongTaskEntries(): RawLongTaskEntry[] {
  const w = window as unknown as LongTaskWindow;
  const entries = w.__sentinelLongTasks?.entries ?? [];
  return entries.map((e) => ({ duration: e.duration, startTime: e.startTime }));
}

export interface RawLongTaskEntry {
  readonly duration: number;
  readonly startTime: number;
}

export function summariseLongTasks(entries: readonly RawLongTaskEntry[]): LongTaskSummary {
  if (entries.length === 0) {
    return { count: 0, total_blocking_ms: 0, longest_ms: 0 };
  }
  let total = 0;
  let longest = 0;
  for (const entry of entries) {
    const dur = Number.isFinite(entry.duration) && entry.duration > 0 ? entry.duration : 0;
    total += dur;
    if (dur > longest) longest = dur;
  }
  return {
    count: entries.length,
    total_blocking_ms: Math.round(total * 100) / 100,
    longest_ms: Math.round(longest * 100) / 100,
  };
}
