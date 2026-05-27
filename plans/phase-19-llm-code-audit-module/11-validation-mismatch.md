# Task 19.11 — Frontend/backend validation mismatch

## Deliverables

- For each form, send a malformed payload directly to the backend (e.g. omit required field) and observe:
  - Frontend rejects (client-side validation present) AND backend accepts → finding `LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS` (high).
  - Backend rejects (4xx) AND frontend would submit it as-is → finding `LLM-VALIDATION-MISMATCH-FRONTEND-MISSING` (medium-high).
- Only runs on local/staging targets; safety policy enforced before sending malformed payloads.

## Acceptance criteria

- Fixture with client-only validation triggers backend-accepts finding.

## Tests required

- `tests/integration/modules/llm_audit/test_validation_mismatch.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31, §6.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
