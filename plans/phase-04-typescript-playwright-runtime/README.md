# Phase 04 — TypeScript Playwright Runtime

## Objective

Build `packages/ts-runtime` — the TypeScript layer Python orchestrates over JSONL. It owns: launching Playwright, running spec files, capturing traces/screenshots/videos/HARs, and emitting structured events back to Python (PRD §11.3, §15, §32, CLAUDE §8, §21).

## PRD / CLAUDE.md references

- PRD §11 Architecture, §15 TS Runtime, §27 Example Generated Test.
- CLAUDE.md §7 Architecture (Python ↔ TS contract), §8 Runtime Ownership, §21 TS / Playwright rules.

## Sub-phases & tasks

1. `01-package-skeleton.md` — `packages/ts-runtime` boots; `tsc`/`vitest` green.
2. `02-helpers.md` — `@sentinelqa/playwright` exports (`sentinelStep`, `captureEvidence`, `redactedNetwork`).
3. `03-runner-binary.md` — `sentinel-ts` CLI invoked by Python; reads run config, runs Playwright, writes JSONL events.
4. `04-jsonl-protocol.md` — Python↔TS protocol versioning + schema (`packages/shared-schema/ts-events.schema.json`).
5. `05-evidence-capture.md` — trace/screenshot/video/HAR/console hooks always on for failures.
6. `06-locator-utils.md` — semantic-locator helpers consumed by the Generator (Phase 07).
7. `07-tests.md` — vitest unit tests + Playwright self-tests in `packages/ts-runtime/tests/`.

## Definition of Done

- `pnpm -r --filter @sentinelqa/ts-runtime test` green.
- The Python runner (Phase 08) can invoke `sentinel-ts run` and parse the JSONL stream end-to-end.
- Failures always emit trace + screenshot + video paths via JSONL.
- No arbitrary sleeps; only Playwright auto-waiting + assertions (CLAUDE §21).
- No stealth/evasion APIs touched.

## Phase Gate Review

- [ ] TS package builds and tests pass.
- [ ] `sentinel-ts run --help` works.
- [ ] JSONL schema validated by CI.
- [ ] Evidence capture verified on a deliberately failing spec.
- [ ] ADR-0009 (Python↔TS protocol) committed.
- [ ] `STATUS.md` updated.
