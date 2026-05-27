# Task 19.02 — Dead buttons

## Deliverables

- Heuristic: for each interactive element identified during discovery, attempt a passive click via Playwright (only on local/staging; never on prod). Capture:
  - Any network request made within 2 s.
  - Any navigation.
  - Any console error.
  - Any DOM change.
- If none → flag as `LLM-DEAD-BTN`, severity high, confidence proportional to evidence.
- Exclude:
  - Buttons whose role is decorative (e.g. carousels indicators).
  - Disabled buttons.
  - Buttons inside `<details>` / accordions that change DOM without network.

## Acceptance criteria

- Fixture "Save" button without handler → finding.
- Compliant button with handler → no finding.

## Tests required

- `tests/integration/modules/llm_audit/test_dead_buttons.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
