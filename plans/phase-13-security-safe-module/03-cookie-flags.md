# Task 13.03 — Cookie flags

## Deliverables

- Inspect every `Set-Cookie` header and stored cookies.
- For each: check `HttpOnly`, `Secure` (on HTTPS), `SameSite` (`Lax` or `Strict` for auth cookies; `None` only if `Secure`).
- Auth cookies identified via heuristics: name matches `session|auth|jwt|token` OR is set on the login response.
- Findings: missing flag → severity per CLAUDE §24 example (high if it's an auth cookie missing `HttpOnly`/`Secure`).

## Acceptance criteria

- Fixture login that sets a cookie without `Secure` flag triggers a high-severity finding (matches CLAUDE §24 example).

## Tests required

- `tests/integration/modules/security/test_cookies.py`.

## Definition of Done

- [ ] Cookie checks + finding mapping implemented.
- [ ] `STATUS.md` updated.
