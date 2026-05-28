# Task 17.07 — Playwright discovery backend (SPA coverage)

> **Re-homed from Phase 05 by ADR-0010.** Phase 05 shipped an HTTP-first
> discovery MVP because Phase 04's JSONL bridge is one-way and could not
> support a Playwright-driven crawler without a TS-side discovery driver +
> a substantial RPC layer. This task delivers that work in Phase 17 where
> Chromium is already provisioned in CI.

## Objective

Add a second discovery backend that drives `@sentinelqa/ts-runtime` via the
existing Phase 04 JSONL bridge so SentinelQA can crawl client-rendered SPAs
(plain Vite + React, etc.) where the HTTP-first backend produces an empty
`DiscoveryGraph`. The two backends must produce equivalent `DiscoveryGraph`
shapes against the same fixture; downstream modules (Planner, Generator,
LLM-Code Audit) MUST NOT need to know which backend ran.

## Deliverables

- **TS:** new `sentinel-ts discover` subcommand under
  `packages/ts-runtime/src/discover.ts`. Accepts `--url`, `--max-depth`,
  `--max-pages`, `--rate-limit`, `--out-dir`, `--auth-config-path`.
  Drives a single Chromium context, navigates BFS, and emits JSONL events
  (re-uses the Phase 04 event registry — adds two new event kinds
  `discovery.page` and `discovery.endpoint` to `ts-events.schema.json`
  via a schema bump, with the parity test extended).
- **Python:** `engine/discovery/backends/playwright_backend.py` exposing
  `PlaywrightCrawlBackend(CrawlBackend)`. Spawns the TS subprocess,
  consumes events with `engine.orchestrator.ts_bridge.stream_events`,
  and translates them into the same `Route`/`Element`/`Form`/`ApiEndpoint`
  records the HTTP backend produces.
- **Config:** `discovery.engine: http | playwright` becomes live — the
  HTTP-first backend remains default; selecting `playwright` requires
  Chromium to be installed (the existing `sentinel doctor` check). The
  loader already reserves the key per ADR-0010.
- **CI:** new GitHub Actions lane `discovery-playwright (gated)` that runs
  the playwright backend against a small CSR SPA fixture (lives in
  `packages/ts-runtime/fixtures/spa/`). Gated by `SENTINELQA_HAS_CHROMIUM=1`
  to match the existing chromium-smoke pattern from Phase 04.
- **Parity tests:** `tests/integration/discovery/test_backend_parity.py`
  drives both backends against the same SSR fixture and asserts the
  produced `DiscoveryGraph`s are equivalent under a canonical ordering
  (sorted routes/elements/forms/endpoints, IDs stripped before compare).

## Acceptance criteria

- Same SSR fixture: both backends produce equivalent graphs (parity test).
- CSR SPA fixture: the HTTP backend produces an empty graph plus a
  `spa_empty_body` risk finding; the Playwright backend produces a
  non-empty graph with all routes/elements present.
- `sentinel discover --url … --backend playwright` writes the same five
  artifact files (`discovery.json`, `forms.json`, `api.json`, `auth.json`,
  `risk.json`, plus `discovery.report.md`) the Phase 05 MVP wrote.
- The new event kinds are validated by the parity test against
  `packages/shared-schema/ts-events.schema.json`.
- ADR-0010's "follow-up obligations" item 1 is marked Resolved in the
  ADR's history note when this task merges.

## Tests required

- `tests/integration/discovery/test_backend_parity.py` (SSR fixture, both
  backends produce equivalent graphs).
- `tests/integration/discovery/test_playwright_backend_spa.py` (CSR SPA
  fixture, gated by `SENTINELQA_HAS_CHROMIUM=1`).
- `packages/ts-runtime/src/__tests__/discover.test.ts` (CLI smoke,
  argument parsing, event emission).
- Parity-schema test extended to cover `discovery.page` and
  `discovery.endpoint` events.

## PRD / CLAUDE.md references

- PRD §9.1 (Discovery module), §15 (TypeScript Runtime), §21 (CI/CD).
- CLAUDE.md §8 (Runtime ownership), §9 (Module contract), §10
  (Run lifecycle), §17 (Quality gates).
- ADR-0010 (Discovery MVP is HTTP-first; Playwright lands here).

## Definition of Done

- [ ] TS `sentinel-ts discover` subcommand authored and CLI-tested.
- [ ] Python `PlaywrightCrawlBackend` implemented.
- [ ] Backend parity test green against SSR fixture.
- [ ] Gated CSR SPA test green when `SENTINELQA_HAS_CHROMIUM=1`.
- [ ] `discovery.engine: playwright` documented in PRD §9.1 and the
      config example.
- [ ] CI lane `discovery-playwright (gated)` added to
      `.github/workflows/ci.yml`.
- [ ] ADR-0010 history annotated: "Follow-up obligation 1 resolved by
      PR #N (Phase 17 task 07)."
- [ ] `STATUS.md` updated.
