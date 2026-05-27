# Task 20.03 — Wait condition improvement

## Deliverables

- Detect uses of `waitForTimeout` in the failing spec (already forbidden by CLAUDE §21, but legacy/hand-edited code may have them).
- Propose replacement with `expect(locator).toBeVisible()` / `toHaveText(...)` based on the assertion that immediately follows.
- Confidence high when the replacement assertion is unambiguous.

## Acceptance criteria

- Fixture with `await page.waitForTimeout(2000)` followed by an assertion produces a high-confidence proposal.

## Tests required

- `tests/unit/healer/test_wait_replacement.py`.

## PRD / CLAUDE.md references

- PRD §9.6.
- CLAUDE.md §21, §23.

## Definition of Done

- [ ] Replacement logic + tests.
- [ ] `STATUS.md` updated.
