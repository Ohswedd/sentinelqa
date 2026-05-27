# Task 12.02 — Page-level performance budgets

## Deliverables

- TS helper `packages/ts-runtime/src/perf/page_metrics.ts` collecting:
  - LCP (via `PerformanceObserver`).
  - CLS (via Layout Instability API).
  - INP approximation (via `event-timing` API; fall back to FID if INP unavailable).
  - Time to First Byte.
  - DOMContentLoaded / load times.
- Python module `modules/performance/page_budget.py` evaluating per-route metrics against `performance.budgets` in config.
- Run N samples (default 3) per route; report median.
- Findings emitted when metric > budget by configurable margin.

## Acceptance criteria

- Slow fixture page exceeds LCP budget → finding emitted.
- Compliant page produces no perf findings.

## Tests required

- `tests/integration/modules/performance/test_page_budgets.py`.

## PRD / CLAUDE.md references

- PRD §10.5, §17.
- CLAUDE.md §27.

## Definition of Done

- [ ] Metrics collected; budgets evaluated.
- [ ] Tests pass.
- [ ] `STATUS.md` updated.
