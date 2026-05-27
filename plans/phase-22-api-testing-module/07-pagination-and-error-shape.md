# Task 22.07 — Pagination & error shape

## Deliverables

- For paginated endpoints (detected via `?page=`, `?cursor=`, `Link: rel="next"`):
  - Walk pages until end; verify count consistency.
  - Boundary: empty page returns empty array (not error).
- Error shape: ensure all 4xx/5xx responses share a uniform JSON shape (e.g. `{ error: { code, message } }`); inconsistencies → medium finding.

## Acceptance criteria

- Fixture inconsistent error shape triggers finding.

## Tests required

- `tests/integration/modules/api/test_pagination_error.py`.

## PRD / CLAUDE.md references

- PRD §10.3.
- CLAUDE.md §30.

## Definition of Done

- [ ] Checks implemented.
- [ ] `STATUS.md` updated.
