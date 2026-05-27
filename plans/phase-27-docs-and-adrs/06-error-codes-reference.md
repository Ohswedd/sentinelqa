# Task 27.06 — Auto-generated error-codes reference

## Deliverables

- A `make docs:gen-error-codes` target that introspects `engine/errors/codes.py` and writes `apps/docs/src/content/errors.md`.
- CI runs the generator and fails if the page is stale.

## Acceptance criteria

- Adding a new code automatically updates the docs on next CI run.

## PRD / CLAUDE.md references

- CLAUDE.md §32, §34.

## Definition of Done

- [ ] Generator + CI guard.
- [ ] `STATUS.md` updated.
