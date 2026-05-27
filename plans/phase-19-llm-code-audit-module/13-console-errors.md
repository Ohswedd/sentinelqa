# Task 19.13 — Console errors ignored by UI

## Deliverables

- Aggregate console errors captured during runs.
- Flag pages where:
  - Console error severity >= `error` occurs but UI shows success state → finding `LLM-CONSOLE-ERROR-IGNORED` (medium).
  - Unhandled promise rejections → finding `LLM-UNHANDLED-PROMISE` (medium).
- Distinguish from third-party noise (filter out errors from analytics/ads domains by configurable allowlist).

## Acceptance criteria

- Fixture page that logs `console.error` after API failure but shows green check → finding.

## Tests required

- `tests/integration/modules/llm_audit/test_console_errors.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
