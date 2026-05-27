# Task 22.06 — API latency budgets (shared with Phase 12)

## Deliverables

- Reuse the Phase 12.03 latency collector; produce module-level findings if `policy.api_p95_ms` exceeded.
- Avoid duplicate findings: if perf module already raised it, this module references the same finding ID.

## Acceptance criteria

- One finding per slow endpoint across the whole run, not duplicated.

## Tests required

- `tests/integration/modules/api/test_latency.py`.

## PRD / CLAUDE.md references

- PRD §10.3, §10.5.
- CLAUDE.md §27, §30.

## Definition of Done

- [ ] Dedup + tests.
- [ ] `STATUS.md` updated.
