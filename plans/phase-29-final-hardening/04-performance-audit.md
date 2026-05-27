# Task 29.04 — Self-performance audit

## Deliverables

- Measure and document on a reference machine:
  - `python -c "import sentinelqa"` import time (target < 200 ms).
  - `sentinel --version` (target < 300 ms).
  - Full `sentinel audit --url http://localhost:3000` on the Next.js example (target < 10 min).
  - Memory peak (target < 1 GB).
- Add `make bench` running these and emitting a report.

## Acceptance criteria

- Targets met (or noted with justification + tracked issue).

## Definition of Done

- [ ] Bench results committed in `docs/release/perf-audit-<date>.md`.
- [ ] `STATUS.md` updated.
