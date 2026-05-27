# Task 20.02 — Locator repair

## Deliverables

- Given a failed locator + the previous descriptor (from Phase 04 `describeLocator`), search the new DOM for a closest match using:
  - Same role + nearest accessible name (string distance).
  - Same role + same surrounding landmark.
- Confidence:
  - Exact role + name match in same landmark → 0.95.
  - Role match + name fuzzy match → 0.75.
  - Role match only → 0.5.
- Auto-apply threshold: configurable; default 0.9.

## Acceptance criteria

- Fixture where "Sign in" button is renamed "Log in" produces a high-confidence repair.
- Drastic DOM change reduces confidence below threshold → requires review.

## Tests required

- `tests/unit/healer/test_locator_repair.py`.

## PRD / CLAUDE.md references

- PRD §9.6.
- CLAUDE.md §23.

## Definition of Done

- [ ] Repair algorithm + tests.
- [ ] `STATUS.md` updated.
