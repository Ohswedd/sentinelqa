# Task 13.07 — IDOR smoke checks

## Deliverables

- For endpoints that include numeric/UUID IDs in the path, attempt to:
  - Replace `me`/`self` with another user ID (if a second test user is configured).
  - Replace ID with `1` and observe behavior.
- Findings:
  - 200 response for another user's resource as a low-privilege test user → critical IDOR.
  - 403 / 404 / redirect → no finding.
- Requires a second test user configured (`auth.second_user_*_env`). Without it, the check is skipped with an `info`-level note in the result, not a finding.

## Acceptance criteria

- IDOR-vulnerable fixture endpoint triggers critical.
- Compliant endpoint produces no IDOR finding.

## Tests required

- `tests/integration/modules/security/test_idor.py`.

## PRD / CLAUDE.md references

- PRD §10.7.
- CLAUDE.md §26.

## Definition of Done

- [ ] IDOR check implemented.
- [ ] Second-user gating respected.
- [ ] `STATUS.md` updated.
