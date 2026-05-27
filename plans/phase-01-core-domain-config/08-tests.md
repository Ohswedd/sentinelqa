# Task 01.08 — Phase 01 test sweep

## Objective

Treat the test suite for Phase 01 as a first-class deliverable. Every model, validator, policy branch, redaction rule, and error code must have explicit coverage; coverage gate ≥ 95% for `engine/domain`, `engine/config`, `engine/policy`, `engine/errors`, `engine/logging`.

## Prerequisites

- Tasks 01.01–01.07 complete.

## Deliverables

- `tests/unit/domain/` — model instantiation, frozen behavior, round-trip, schema generation.
- `tests/unit/config/` — schema validation, loader, env interpolation, secret safety.
- `tests/unit/policy/` — safety policy branches, forbidden capabilities, audit log, redaction.
- `tests/unit/errors/` — hierarchy, agent-message, rendering.
- `tests/unit/logging/` — modes, redaction filter, audit stream.
- `tests/property/` — hypothesis suites for IDs, redaction, config validation edge cases.
- `tests/golden/config/` — canonical example YAML + expected parsed JSON; locked with golden tests.
- A `pytest -q` run that completes under 30 seconds on a developer laptop (use markers to skip the property tests in fast CI, run them in full CI nightly).
- Coverage report integrated into CI; PR blocked if `engine/domain | engine/config | engine/policy | engine/errors | engine/logging` drops below 95%.

## Steps

1. Audit Phase 01 code for any branch or model not yet exercised; add tests.
2. Capture golden JSON for the example config in `tests/golden/config/example.golden.json`. Provide a `make update-goldens` task that regenerates them deliberately.
3. Add the coverage threshold to `pyproject.toml` (`tool.coverage.report.fail_under = 95` for the listed packages).
4. Tag slow property tests with `@pytest.mark.slow` and exclude from default `pytest`.
5. Add a `make test:fast` target (no slow) and a `make test:full` target (everything).

## Acceptance criteria

- `make test:fast` < 30 s.
- `make test:full` includes property and golden tests, all green.
- Coverage thresholds enforced; deliberate uncovered branch fails CI.
- Goldens regenerate cleanly with `make update-goldens` only when explicitly invoked.

## Tests required

- (This task **is** the tests; verified by coverage.)

## PRD / CLAUDE.md references

- CLAUDE.md §16 Testing standard, §17 Quality gates.

## Definition of Done

- [ ] All listed test packages exist.
- [ ] Coverage ≥ 95% in scoped packages.
- [ ] Goldens locked and stable.
- [ ] `make test:fast` and `make test:full` both green.
- [ ] `STATUS.md` updated; Phase 01 ready for gate review.
