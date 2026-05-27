# Task 04.07 — Phase 04 test sweep

## Objective

Lock in the TS runtime with unit, integration, and a Playwright smoke test against a tiny fixture app.

## Deliverables

- `packages/ts-runtime/tests/` covering every helper and CLI command.
- `packages/ts-runtime/fixtures/sample-app/` — a tiny static site (or Playwright-served `vite` app) used by integration tests.
- A cross-language parity test for the JSONL protocol (already touched in 04.04 — re-confirm here).
- Coverage gate ≥ 85% for `packages/ts-runtime/src/`.
- Playwright smoke: launches Chromium, runs one spec, captures evidence — all in CI.

## Steps

1. Add the fixture app. Keep it under 10 files.
2. Add `vitest` unit tests for every helper.
3. Add `@playwright/test` integration tests for `sentinel-ts run`.
4. Configure `vitest.config.ts` with coverage threshold.
5. Wire into root `pnpm -r run test`.

## Acceptance criteria

- All tests pass locally and in CI.
- Coverage gate met.
- Smoke runs in under 90 seconds in CI.

## PRD / CLAUDE.md references

- CLAUDE.md §16 Testing, §17 Quality gates, §21 TS rules.

## Definition of Done

- [ ] Unit + integration tests pass.
- [ ] Coverage gate met.
- [ ] Smoke run green in CI.
- [ ] `STATUS.md` updated; Phase 04 ready for gate.
