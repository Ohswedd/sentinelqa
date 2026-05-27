# Task 13.13 — Phase 13 test sweep

## Deliverables

- Unit + integration tests as listed in 13.01–13.12.
- A fixture "vulnerable app" providing each vulnerability class (kept locally only; never deployed; under `packages/ts-runtime/fixtures/sample-app-vulnerable/`).
- Coverage gate ≥ 90% for `modules/security/`.
- Adversarial test: attempt to run security against `https://example.com` without allowlist → must refuse and exit 4.

## Acceptance criteria

- All tests pass.
- Coverage met.
- Adversarial refusal test green.

## Definition of Done

- [ ] All security tests pass.
- [ ] Coverage met.
- [ ] Refusal verified.
- [ ] `STATUS.md` updated; Phase 13 ready for gate.
