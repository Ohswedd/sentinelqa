# Task 20.05 — Repair proposal schema

## Deliverables

- `packages/shared-schema/repair-suggestion.schema.json` matching CLAUDE §23 contract:
  - `original_behavior`, `proposed_change`, `confidence`, `reason`, `evidence`, `requires_human_review`, plus `target_test`, `kind` (`locator`/`wait`/`fixture`/`assertion`), `unified_diff` (patch).
- Persisted under `<run-dir>/healer/<suggestion-id>.json` and surfaced in the HTML report.

## Acceptance criteria

- Generated proposals validate against the schema.

## Tests required

- `tests/golden/healer/test_proposal_schema.py`.

## PRD / CLAUDE.md references

- PRD §9.6, §18.
- CLAUDE.md §23.

## Definition of Done

- [ ] Schema + writer.
- [ ] `STATUS.md` updated.
