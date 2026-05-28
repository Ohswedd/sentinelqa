import { afterEach, describe, expect, it } from 'vitest';

import { prepLongTaskObserver, readLongTaskEntries, summariseLongTasks } from '../long_tasks.js';

describe('summariseLongTasks', () => {
  it('returns zeros for empty input', () => {
    expect(summariseLongTasks([])).toEqual({ count: 0, total_blocking_ms: 0, longest_ms: 0 });
  });

  it('sums durations and finds the longest entry', () => {
    const summary = summariseLongTasks([
      { duration: 60, startTime: 100 },
      { duration: 90, startTime: 200 },
      { duration: 75.123, startTime: 400 },
    ]);
    expect(summary.count).toBe(3);
    expect(summary.total_blocking_ms).toBe(225.12);
    expect(summary.longest_ms).toBe(90);
  });

  it('drops invalid durations', () => {
    const summary = summariseLongTasks([
      { duration: 50, startTime: 0 },
      { duration: Number.POSITIVE_INFINITY, startTime: 0 },
      { duration: -10, startTime: 0 },
    ]);
    expect(summary.count).toBe(3); // count is honest even for invalids
    expect(summary.total_blocking_ms).toBe(50);
    expect(summary.longest_ms).toBe(50);
  });
});

describe('prepLongTaskObserver + readLongTaskEntries', () => {
  let originalPO: unknown;
  let originalWindow: unknown;
  let fired: ((list: { getEntries: () => unknown[] }) => void) | null = null;

  afterEach(() => {
    (globalThis as { PerformanceObserver?: unknown }).PerformanceObserver = originalPO as
      | typeof PerformanceObserver
      | undefined;
    (globalThis as { window?: unknown }).window = originalWindow;
    delete (globalThis as unknown as { __sentinelLongTasks?: unknown }).__sentinelLongTasks;
    fired = null;
  });

  function install(): void {
    originalPO = (globalThis as { PerformanceObserver?: unknown }).PerformanceObserver;
    originalWindow = (globalThis as { window?: unknown }).window;
    class FakeObserver {
      private readonly cb: (list: { getEntries: () => unknown[] }) => void;
      constructor(cb: (list: { getEntries: () => unknown[] }) => void) {
        this.cb = cb;
        fired = cb;
      }
      observe(): void {
        /* noop */
      }
    }
    (globalThis as { PerformanceObserver?: unknown }).PerformanceObserver =
      FakeObserver as unknown as typeof PerformanceObserver;
    (globalThis as { window?: unknown }).window = globalThis;
  }

  it('records long-task entries observed after prep', () => {
    install();
    prepLongTaskObserver();
    fired?.({
      getEntries: () => [
        { duration: 60, startTime: 1 },
        { duration: 90, startTime: 2 },
      ],
    });
    const entries = readLongTaskEntries();
    expect(entries).toHaveLength(2);
    expect(entries[0]?.duration).toBe(60);
  });

  it('returns empty array when no observer has fired', () => {
    install();
    prepLongTaskObserver();
    expect(readLongTaskEntries()).toEqual([]);
  });

  it('does not throw when PerformanceObserver constructor fails', () => {
    install();
    (globalThis as { PerformanceObserver?: unknown }).PerformanceObserver = (() => {
      throw new Error('unsupported');
    }) as unknown as typeof PerformanceObserver;
    expect(() => prepLongTaskObserver()).not.toThrow();
  });
});
