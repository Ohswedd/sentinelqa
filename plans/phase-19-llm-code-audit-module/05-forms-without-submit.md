# Task 19.05 — Forms without functioning submit

## Deliverables

- Use Phase 05 forms inventory: if `submit_handler_present == false` OR a form's submit produced no network request during exercised flows, flag.
- Distinguish from "form not exercised" — only flag forms the planner attempted.
- Finding: `LLM-FORM-NO-SUBMIT`, severity high.

## Acceptance criteria

- Fixture form with `onSubmit` removed triggers finding.
- Working form does not.

## Tests required

- `tests/integration/modules/llm_audit/test_forms_no_submit.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
