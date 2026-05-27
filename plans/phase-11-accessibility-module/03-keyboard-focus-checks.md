# Task 11.03 — Keyboard navigation & focus

## Deliverables

- TS helper that tabs through every focusable element on a page, capturing tab order and focus-visible state.
- Detect:
  - Skipped elements (tabindex anomalies).
  - Focus traps (modal blocks remain unable to escape via keyboard).
  - Missing focus-visible styling (computed style check).
- Findings categorized as `keyboard-navigation`, `focus-trap`, `focus-visible`.

## Acceptance criteria

- Fixture modal without focus trap → finding emitted.
- Compliant modal → no finding.

## Tests required

- `tests/integration/modules/accessibility/test_keyboard.py`.

## PRD / CLAUDE.md references

- PRD §10.4.
- CLAUDE.md §28.

## Definition of Done

- [ ] Keyboard checks implemented and tested.
- [ ] `STATUS.md` updated.
