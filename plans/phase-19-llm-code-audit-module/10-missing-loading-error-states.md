# Task 19.10 — Missing loading / error states

## Deliverables

- During runner flows, deliberately delay (route block via Playwright `route.fulfill` with `delay`) or fail (`status: 500`) target API calls; observe UI:
  - No loading indicator within X ms → `LLM-NO-LOADING-STATE` (medium).
  - No error message or empty-state UI on 500 → `LLM-NO-ERROR-STATE` (high).
- Distinguish from happy-path success (control sample).

## Acceptance criteria

- Fixture page with no loading state during slow API → finding.
- Compliant page with skeleton/spinner → no finding.

## Tests required

- `tests/integration/modules/llm_audit/test_loading_error_states.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
