# Task 05.02 — DOM interaction map

## Objective

For every crawled page, extract a structured map of interactive elements (buttons, links, inputs, forms, ARIA controls), console errors, and network failures. The map feeds the Planner and the LLM-code audit.

## Deliverables

- `engine/discovery/dom_map.py` building `Element` records from DOM snapshots produced by the TS runtime.
- Element fields: role, accessible name, tag, selector (semantic first), location (route), tags (e.g. `clickable`, `disabled`, `hidden`).
- A separate `interaction_attempt` pass: for elements that look like buttons, attempt a passive interaction (`hover` only — not `click`, to keep discovery non-destructive) and record any console errors / network failures triggered.
- Captures repeated components (heuristic: same role + accessible name appearing on ≥ 3 pages → likely a shared component, recorded as `RepeatedComponent`).
- Captures unreachable internal links (anchor `href` points at a route that returns 4xx).

## Steps

1. Add a TS helper that returns a structured DOM map per page.
2. Wire it into the crawler so each page emits a DOM map event.
3. Python aggregates and deduplicates.
4. Add detection for missing accessible labels (also reused by Phase 11 a11y).

## Acceptance criteria

- A page with 3 buttons and 2 forms produces exactly 5 distinct elements with semantic roles.
- Unreachable links collected.

## Tests required

- `tests/integration/discovery/test_dom_map.py` — against fixture pages.
- `tests/unit/discovery/test_repeated_component.py`.

## PRD / CLAUDE.md references

- PRD §9.1.
- CLAUDE.md §9 Module contract.

## Definition of Done

- [ ] DOM map per page produced.
- [ ] Repeated components and unreachable links detected.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
