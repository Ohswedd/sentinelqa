# Task 11.02 — axe-core integration

## Deliverables

- TS helper `packages/ts-runtime/src/a11y/axe.ts` injecting `axe-core` (pin the version in `package.json`) into a page and returning a structured violation list.
- Python wrapper in `modules/accessibility/axe_runner.py` invoking the helper per discovered route.
- Configurable rule set in `sentinel.config.yaml` (`accessibility.axe.tags` defaults to `["wcag2a","wcag2aa","best-practice"]`).
- Per-page result saved under `<run-dir>/a11y/<route-slug>.json`.

## Acceptance criteria

- Fixture compliant page: 0 violations.
- Fixture non-compliant page (missing alt text, low contrast): violations present with the expected rule IDs.

## Tests required

- `tests/integration/modules/accessibility/test_axe_runner.py`.

## PRD / CLAUDE.md references

- PRD §10.4.
- CLAUDE.md §28.

## Definition of Done

- [ ] Axe runner stable on fixture.
- [ ] `STATUS.md` updated.
