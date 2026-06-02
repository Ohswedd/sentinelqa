# @sentinelqa/rum

Real-User Monitoring SDK that emits SentinelQA-compatible JSONL events
from the browser. Zero deps, ESM, drops into any modern frontend.

The receiver (`engine.rum.ingest_jsonl`) writes the events into the
same artifact tree as a synthetic run, so the reporter, scoring, and
gating logic work unchanged on real-user data.

## Install

```bash
pnpm add @sentinelqa/rum
# or npm install @sentinelqa/rum
```

## Use

```ts
import { initRum, emit, shutdown } from '@sentinelqa/rum';

initRum({
  endpoint: 'https://your-app.example.com/rum',
  sampleRate: 0.1, // capture 10 % of sessions
});

// Optional: emit a custom event.
emit('user.action', { name: 'checkout-clicked' });

// Optional: graceful shutdown (e.g. on a SPA unmount).
window.addEventListener('pagehide', shutdown);
```

The SDK auto-wires:

- a `run.start` on `initRum`,
- a `page.view` snapshot of `window.location.pathname`,
- `page.error` from `window.error` + `unhandledrejection`,
- `run.end` on `shutdown()`.

It flushes on:

- `beforeunload` (via `navigator.sendBeacon`),
- `visibilitychange` → hidden,
- every `flushIntervalMs` (default 30 s),
- when the buffer hits `maxBufferSize` (default 200).

The SDK never throws into the host app; a failed `fetch` is swallowed.

## Schema

The on-wire envelope is the same as the synthetic Playwright runner
(see `engine/orchestrator/ts_bridge.py`):

```jsonc
{
  "schema_version": "1",
  "type": "page.error",
  "seq": 12,
  "ts": "2026-06-02T12:00:03.142Z",
  "route": "/checkout",
  "message": "Cannot read property 'price' of undefined",
}
```

Unknown event types are recorded verbatim; the receiver is forward-compatible.

## Status

`v1.9.0` ships the MVP: SDK + receiver + ingest CLI. Sampling, replay,
session correlation, and a hosted ingest endpoint are downstream work.
