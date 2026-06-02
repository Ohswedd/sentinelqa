// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.
//
// SentinelQA RUM browser SDK (v1.9.0, phase 39).
//
// Emits JSONL events in the same envelope shape the synthetic runner
// emits (engine/orchestrator/ts_bridge.py + packages/ts-runtime/src/protocol.ts).
// The receiver at engine/rum/ingest.py consumes the output as if it
// were a synthetic run.
//
// Drop into your app:
//
//   import { initRum } from "@sentinelqa/rum";
//
//   initRum({
//     endpoint: "https://your-app.example.com/rum",
//     sampleRate: 0.1,
//   });
//
// Zero dependencies; works in any modern evergreen browser. The SDK
// flushes events on:
//
//   * a `beforeunload` listener (final flush — uses navigator.sendBeacon).
//   * a visibility-change listener (background → foreground transition).
//   * a configurable interval (default 30 s).

export const RUM_SCHEMA_VERSION = '1';

export type RumEventKind =
  | 'run.start'
  | 'run.end'
  | 'page.view'
  | 'page.error'
  | 'network.request'
  | 'network.response'
  | 'network.failure'
  | 'console'
  | 'user.action';

export interface RumEnvelope {
  readonly schema_version: typeof RUM_SCHEMA_VERSION;
  readonly type: RumEventKind | (string & {});
  readonly seq: number;
  readonly ts: string;
}

export interface RumConfig {
  /** HTTPS endpoint that ingests the JSONL stream (POST, body: JSONL). */
  readonly endpoint: string;
  /** Fraction of sessions to record. 0.0–1.0; default 1.0. */
  readonly sampleRate?: number;
  /** Flush interval in milliseconds. Default 30_000 (30s). */
  readonly flushIntervalMs?: number;
  /** Maximum events kept in memory before forced flush. Default 200. */
  readonly maxBufferSize?: number;
  /** When false, the SDK silently no-ops. Default true. */
  readonly enabled?: boolean;
}

interface RumState {
  config: Required<RumConfig>;
  buffer: (RumEnvelope & Record<string, unknown>)[];
  seq: number;
  flushTimer: number | null;
  active: boolean;
}

const DEFAULTS: Required<Omit<RumConfig, 'endpoint'>> = {
  sampleRate: 1.0,
  flushIntervalMs: 30_000,
  maxBufferSize: 200,
  enabled: true,
};

let state: RumState | null = null;

/** Initialise the SDK. Idempotent — calling twice is a no-op. */
export function initRum(config: RumConfig): void {
  if (state) {
    return;
  }
  const fullConfig: Required<RumConfig> = { ...DEFAULTS, ...config };

  if (!fullConfig.enabled) {
    return;
  }
  if (Math.random() >= fullConfig.sampleRate) {
    return;
  }

  state = {
    config: fullConfig,
    buffer: [],
    seq: 0,
    flushTimer: null,
    active: true,
  };

  emit('run.start', {});
  wireBrowserListeners();
  scheduleFlush();
}

/** Manually record one event. */
export function emit(type: RumEventKind | (string & {}), payload: Record<string, unknown>): void {
  if (!state?.active) {
    return;
  }
  state.seq += 1;
  state.buffer.push({
    schema_version: RUM_SCHEMA_VERSION,
    type,
    seq: state.seq,
    ts: new Date().toISOString(),
    ...payload,
  });
  if (state.buffer.length >= state.config.maxBufferSize) {
    void flush();
  }
}

/** Flush the buffer to the receiver. */
export async function flush(): Promise<void> {
  if (!state || state.buffer.length === 0) {
    return;
  }
  const batch = state.buffer.splice(0, state.buffer.length);
  const body = batch.map((event) => JSON.stringify(event)).join('\n') + '\n';

  // Prefer sendBeacon on unload paths; otherwise fall back to fetch.
  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    const blob = new Blob([body], { type: 'application/x-ndjson' });
    const queued = navigator.sendBeacon(state.config.endpoint, blob);
    if (queued) {
      return;
    }
  }

  try {
    await fetch(state.config.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-ndjson' },
      body,
      keepalive: true,
    });
  } catch {
    // Swallow — RUM must never crash the host app.
  }
}

/** Stop the SDK. The next event after this is dropped on the floor. */
export function shutdown(): void {
  if (!state) {
    return;
  }
  emit('run.end', {});
  void flush();
  if (state.flushTimer !== null) {
    clearInterval(state.flushTimer);
  }
  state.active = false;
  state = null;
}

function wireBrowserListeners(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.addEventListener('error', (event: ErrorEvent) => {
    const errorMessage =
      typeof event.error === 'object' && event.error !== null && 'message' in event.error
        ? String((event.error as { message: unknown }).message)
        : '';
    emit('page.error', {
      message: String(event.message ?? errorMessage),
      route: window.location.pathname,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  });

  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    emit('page.error', {
      message: `unhandledrejection: ${String(event.reason)}`,
      route: window.location.pathname,
    });
  });

  window.addEventListener('beforeunload', () => {
    void flush();
  });

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        void flush();
      }
    });
  }

  // Snapshot the current route.
  emit('page.view', { route: window.location.pathname });
}

function scheduleFlush(): void {
  if (!state || typeof window === 'undefined') {
    return;
  }
  state.flushTimer = window.setInterval(() => {
    void flush();
  }, state.config.flushIntervalMs);
}
