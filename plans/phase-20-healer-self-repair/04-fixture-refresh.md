# Task 20.04 — Fixture refresh

## Deliverables

- When a data fixture (`seededRecord`) fails because the seeded entity is missing or the API contract changed, the healer proposes:
  - Re-running the seed function.
  - Regenerating the fixture data file from the latest OpenAPI/GraphQL schema.
- Output is always a proposal — never automatically applied to the database.

## Acceptance criteria

- Fixture missing row → proposal includes the re-seed action.

## Tests required

- `tests/unit/healer/test_fixture_refresh.py`.

## PRD / CLAUDE.md references

- PRD §9.6.
- CLAUDE.md §23.

## Definition of Done

- [ ] Refresh proposals + tests.
- [ ] `STATUS.md` updated.
