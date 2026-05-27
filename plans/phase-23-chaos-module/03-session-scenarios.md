# Task 23.03 — Session scenarios

## Deliverables

- Inject `Authorization: Bearer expired.token.here` and verify UI redirects to login (not blank-screens).
- Strip permission claims from a JWT (sandbox-mode only) and verify UI denies access gracefully.
- Findings: `chaos-session-expired-no-redirect`, `chaos-permission-missing-bad-ux`.

## Acceptance criteria

- Fixture with bad UX on expired session triggers finding.

## Tests required

- `tests/integration/modules/chaos/test_session.py`.

## Definition of Done

- [ ] Scenarios + tests.
- [ ] `STATUS.md` updated.
