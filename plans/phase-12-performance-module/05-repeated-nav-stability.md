# Task 12.05 — Repeated navigation stability

## Deliverables

- Visit the same route N times (default 5); collect memory and DOM-node counts via `performance.memory` + `document.getElementsByTagName('*').length`.
- Flag rising memory or growing DOM-node counts as `potential-memory-leak` finding (low confidence — heuristic).

## Acceptance criteria

- Stable fixture has no leak finding.
- Leaky fixture (deliberate dangling listeners) flagged.

## Tests required

- `tests/integration/modules/performance/test_repeated_nav.py`.

## PRD / CLAUDE.md references

- PRD §10.5.
- CLAUDE.md §27.

## Definition of Done

- [ ] Repeated-nav loop and leak heuristic implemented.
- [ ] `STATUS.md` updated.
