# Task 19.06 — Missing CRUD edges

## Deliverables

- Detect when create works but read/update/delete is missing for the same resource.
- Strategy:
  - From discovery: REST patterns (`POST /api/users` and `GET /api/users/[id]`).
  - From UI: `Add` / `Create` buttons present but no `Edit`/`Delete` counterparts within a resource list.
- Findings: `LLM-INCOMPLETE-CRUD-<resource>`, medium-high severity.

## Acceptance criteria

- Fixture with create-only resource triggers finding.

## Tests required

- `tests/integration/modules/llm_audit/test_incomplete_crud.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
