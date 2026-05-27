# Task 03.08 — Phase 03 schema test sweep

## Objective

Make schema drift impossible. Every emitted artifact has goldens + schema validation in CI, and any change requires a deliberate `make update-goldens` invocation.

## Deliverables

- `tests/golden/reports/` containing locked goldens for every writer and every interesting state (passing, failing, unsafe_blocked, dry_run).
- A `make update-goldens` task with a confirmation prompt (or `--force` flag) that regenerates them.
- CI step that runs schema validation for every committed `*.schema.json` and `*.golden.json`.
- Property tests (hypothesis) that generate random Findings and assert the writers produce valid JSON/XML/SARIF.

## Acceptance criteria

- A deliberate change to a writer that breaks a golden fails CI.
- `make update-goldens` regenerates them; the diff is the only change in a follow-up commit.
- Schema validation catches a malformed test fixture.

## Tests required

- (This task is the test suite.)

## PRD / CLAUDE.md references

- CLAUDE.md §16 Testing, §17 Quality gates.

## Definition of Done

- [ ] Goldens for every artifact and state.
- [ ] CI validates schemas and goldens.
- [ ] Property tests green.
- [ ] `STATUS.md` updated; Phase 03 ready for gate.
