# Task 25.07 — Phase 25 test sweep

## Deliverables

- All listed mock tests.
- A guard test: CI never receives real credentials for these integrations (env vars must be unset in CI; tests fail if they leak).
- Coverage gate ≥ 80% for `integrations/`.

## Definition of Done

- [ ] All tests pass.
- [ ] Credential-leak guard active.
- [ ] `STATUS.md` updated; Phase 25 ready for gate.
