# Task 21.04 — Dynamic-content masking

## Deliverables

- Config: `visual.masks: list[{ route, selector, reason }]`.
- TS helper hides matched elements (sets visibility hidden) before capture.
- Optional auto-mask for known patterns (clocks via `<time>` tag, animated SVG ads, etc.) via `visual.auto_mask: true`.

## Acceptance criteria

- Fixture page with a clock that updates every second is stable across runs when masked.

## Tests required

- `tests/integration/modules/visual/test_masking.py`.

## PRD / CLAUDE.md references

- PRD §10.6.
- CLAUDE.md §29.

## Definition of Done

- [ ] Masking implemented.
- [ ] `STATUS.md` updated.
