# Task 20.01 — Healer module skeleton

## Deliverables

- `engine/healer/__init__.py` exposing `Healer` with `propose(failure, ctx) -> list[RepairSuggestion]`.
- Healer is invoked by the Analyzer (Phase 09) for `test_bug` categorized failures.
- Each suggestion typed via the Phase 01 `RepairSuggestion` model.

## Tests required

- `tests/unit/healer/test_skeleton.py`.

## PRD / CLAUDE.md references

- PRD §9.6.
- CLAUDE.md §23.

## Definition of Done

- [ ] Skeleton committed.
- [ ] `STATUS.md` updated.
