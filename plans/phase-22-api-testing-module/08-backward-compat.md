# Task 22.08 — Backward compatibility checks

## Deliverables

- When prior `api-schema.json` exists in `.sentinel/runs/`, diff current vs. previous:
  - Removed endpoints → high.
  - Removed required response fields → high.
  - Changed types → high.
  - Added required request fields → medium-high.
- Findings reference the diff.

## Acceptance criteria

- Diffing two intentionally-different OpenAPI docs surfaces every breaking change.

## Tests required

- `tests/unit/modules/api/test_backward_compat.py`.

## PRD / CLAUDE.md references

- PRD §10.3.
- CLAUDE.md §30.

## Definition of Done

- [ ] Diff implemented + tested.
- [ ] `STATUS.md` updated.
