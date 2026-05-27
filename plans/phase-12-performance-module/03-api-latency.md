# Task 12.03 — API latency budgets

## Deliverables

- Hook into the TS network instrumentation; collect durations per API endpoint.
- Compute P50/P95 across observations per endpoint per run.
- Budget evaluation: `performance.budgets.api_p95_ms`.
- Findings name the endpoint template (`/api/users/[id]`).

## Acceptance criteria

- Slow endpoint fixture exceeds p95 budget → finding emitted.

## Tests required

- `tests/integration/modules/performance/test_api_latency.py`.

## PRD / CLAUDE.md references

- PRD §10.5.
- CLAUDE.md §27.

## Definition of Done

- [ ] P50/P95 computed; budget evaluated.
- [ ] `STATUS.md` updated.
