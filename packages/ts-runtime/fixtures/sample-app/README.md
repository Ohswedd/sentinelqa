# Sample app — SentinelQA TS runtime fixture

A tiny static site used by the smoke test. Two pages:

- `index.html` — landing page with semantic anchors (heading, nav, labeled email input, button).
- `success.html` — destination of the submit action.

Served by Node's built-in `http.createServer` from
`fixtures/serve.mjs`; no external dependencies. The Playwright smoke
spec (`fixtures/specs/login.spec.ts`) navigates the flow, captures
evidence on failure, and emits SentinelQA JSONL events via the
`SentinelReporter`.

The smoke spec is **gated**: it runs only when Chromium is installed
locally (set `SENTINELQA_HAS_CHROMIUM=1`). CI installs Chromium in a
dedicated lane; the default `pnpm --filter @sentinelqa/ts-runtime
test` does NOT spawn a browser.
