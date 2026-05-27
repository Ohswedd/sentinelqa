# Task 12.04 — Bundle size & CPU blocking

## Deliverables

- Collect JS bundle size from network responses (filter by `content-type: application/javascript`); sum transferred + uncompressed sizes.
- Detect long-tasks via `PerformanceObserver({ entryTypes: ['longtask'] })`; flag when total > budget.
- Findings: `bundle-size-exceeded`, `cpu-blocking-tasks`.

## Acceptance criteria

- Fixture with deliberately large bundle triggers `bundle-size-exceeded`.
- Fixture with sync `while(true)` blocked task triggers CPU finding.

## Tests required

- `tests/integration/modules/performance/test_bundle_cpu.py`.

## PRD / CLAUDE.md references

- PRD §10.5.
- CLAUDE.md §27.

## Definition of Done

- [ ] Collectors + budgets working.
- [ ] `STATUS.md` updated.
