# Task 07.03 — Fixtures (auth + data)

## Objective

Generate reusable Playwright fixtures so generated tests don't repeat boilerplate (auth, data setup/teardown).

## Deliverables

- `engine/generator/fixtures.py` emitting:
  - `tests/sentinel/fixtures/auth.ts` — `authenticatedPage` fixture that performs login once per worker (Playwright `storageState`).
  - `tests/sentinel/fixtures/data.ts` — `freshUser`, `seededRecord`, etc. — opt-in fixtures that create data via the API map (Phase 05 detected endpoints) and clean up after.
  - `tests/sentinel/setup/global-setup.ts` — runs auth-state generation once at suite start.
  - `tests/sentinel/setup/global-teardown.ts` — runs cleanup.
- Fixture generation uses env-var names from the config; **never** hardcodes credentials.

## Steps

1. Implement fixture generators with config-driven endpoint references.
2. Generated fixtures must compile and run on the fixture app.
3. Add safeguards: data fixtures abort if config's safety policy says destructive operations aren't allowed for the current target mode.

## Acceptance criteria

- `tests/sentinel/fixtures/auth.ts` works against fixture app.
- Data fixtures clean up after themselves.

## Tests required

- `tests/golden/generator/test_fixtures.py`.
- `tests/integration/generator/test_fixtures_run.py`.

## PRD / CLAUDE.md references

- PRD §9.3, §15.
- CLAUDE.md §21.

## Definition of Done

- [ ] Auth + data fixtures generated and tested.
- [ ] No hardcoded credentials.
- [ ] `STATUS.md` updated.
