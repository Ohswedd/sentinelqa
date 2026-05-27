# Task 08.05 — Result collection & normalization

## Objective

Aggregate the JSONL stream + Playwright artifacts into a normalized `ModuleResult` consumable by the Analyzer (Phase 09), the Reporter (Phase 03), and the Score module (Phase 14).

## Deliverables

- `engine/runner/results.py` exposing `aggregate(events: AsyncIterator[Event]) -> ModuleResult`.
- Aggregator:
  - Builds per-test records (status, duration, retries, evidence paths).
  - Aggregates timings into module-level metrics (P50/P95 duration).
  - Captures unhandled errors into `ModuleResult.errors`.
  - Records browser/version/OS context for reproducibility.
- Persists `module-results/<module-name>.json` artifact per module.

## Steps

1. Implement aggregation.
2. Persist per-module artifact.
3. Add tests using fixture JSONL streams.

## Acceptance criteria

- A known JSONL stream produces a stable `ModuleResult`.
- Aggregator handles partial streams (process killed mid-run) gracefully.

## Tests required

- `tests/unit/runner/test_aggregate.py`.
- `tests/integration/runner/test_partial_stream.py`.

## PRD / CLAUDE.md references

- PRD §9.4, §20.
- CLAUDE.md §9, §11.

## Definition of Done

- [ ] Aggregator stable on full + partial streams.
- [ ] `STATUS.md` updated.
