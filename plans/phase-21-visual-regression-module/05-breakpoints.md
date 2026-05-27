# Task 21.05 — Responsive breakpoints

## Deliverables

- Config: `visual.viewports: list[{ name, width, height }]`. Defaults: `mobile (375x812)`, `tablet (768x1024)`, `desktop (1280x800)`.
- For each route in scope, capture per viewport. Findings include the viewport.

## Acceptance criteria

- Fixture capture produces baselines for each viewport.

## Tests required

- `tests/integration/modules/visual/test_breakpoints.py`.

## PRD / CLAUDE.md references

- PRD §10.6.
- CLAUDE.md §29.

## Definition of Done

- [ ] Viewports implemented.
- [ ] `STATUS.md` updated.
