# Task 22.05 — Auth tests

## Deliverables

- For each authenticated endpoint:
  - Send anonymous → expect 401/403.
  - Send expired token → expect 401.
  - Send token for another user → expect 403/404 (IDOR overlap with Phase 13.07).
- For endpoints behind role, send low-priv user → expect 403.
- Findings: any 200 in unauthorized cases.

## Acceptance criteria

- Fixture endpoint returning 200 to anonymous → critical finding.

## Tests required

- `tests/integration/modules/api/test_auth.py`.

## PRD / CLAUDE.md references

- PRD §10.3, §10.7.
- CLAUDE.md §30.

## Definition of Done

- [ ] Auth tests implemented.
- [ ] `STATUS.md` updated.
