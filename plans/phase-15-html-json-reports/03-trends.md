# Task 15.03 — Trends from local history

## Deliverables

- `engine/reporter/trends.py` reading the last N runs from `.sentinel/runs/` and producing:
  - Score-over-time series.
  - Per-module pass-rate over time.
  - Top recurring finding IDs.
- Trends embedded in `report.html`.
- No external storage; uses local run directory only (Phase 4 cloud is later).

## Acceptance criteria

- With 0 prior runs: trends section hidden.
- With ≥ 2 prior runs: trends rendered with a small SVG sparkline (no JS chart libs).

## Tests required

- `tests/integration/reporter/test_trends.py`.

## PRD / CLAUDE.md references

- PRD §9.7, §38.
- CLAUDE.md §38, §41.

## Definition of Done

- [ ] Trends compute correctly.
- [ ] Sparkline renders without JS lib.
- [ ] `STATUS.md` updated.
