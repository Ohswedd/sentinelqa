# Task 22.04 — Negative cases

## Deliverables

- For each endpoint with a schema, generate negative variants:
  - Missing required field.
  - Wrong type.
  - Out-of-range integer.
  - Oversized string (within rate-limit safe bounds; default 16 KB).
- Expected: backend returns 4xx with structured error.
- Findings:
  - 5xx on negative input → high.
  - 200 on missing required field → high (validation gap).
  - Inconsistent error shape → medium.

## Acceptance criteria

- Fixture endpoint accepting missing required field triggers finding.

## Tests required

- `tests/integration/modules/api/test_negative_cases.py`.

## PRD / CLAUDE.md references

- PRD §10.3.
- CLAUDE.md §30.

## Definition of Done

- [ ] Negative-case generation + tests.
- [ ] `STATUS.md` updated.
