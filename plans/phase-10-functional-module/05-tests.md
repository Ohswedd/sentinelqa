# Task 10.05 — Phase 10 test sweep

## Objective

Cover the functional module end-to-end with both passing and failing scenarios.

## Deliverables

- A deliberately broken fixture variant in `packages/ts-runtime/fixtures/sample-app-broken/` (e.g. login redirects loop, CRUD edit endpoint 500s). Used by tests to verify the failure path.
- Tests verifying:
  - Happy run on `sample-app` exits 0; finding count = 0 of severity ≥ medium.
  - Broken run on `sample-app-broken` exits with quality-gate failure; findings include the broken behaviors with full evidence.
- Coverage gate ≥ 90% for `modules/functional/`.

## Acceptance criteria

- Both fixtures produce expected results.
- Coverage met.

## PRD / CLAUDE.md references

- CLAUDE.md §16, §17.

## Definition of Done

- [ ] Both fixtures + tests committed.
- [ ] Coverage gate met.
- [ ] `STATUS.md` updated; Phase 10 ready for gate.
