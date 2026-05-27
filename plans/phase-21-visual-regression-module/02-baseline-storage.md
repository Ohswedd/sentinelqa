# Task 21.02 — Baseline storage

## Deliverables

- Default path `.sentinel/baselines/<browser>/<viewport>/<route-slug>.png`. Configurable via `visual.baselines_dir`.
- Baseline metadata (`baselines.json`): per-image checksum, captured-at, captured-by-run-id, masks applied.
- Baselines committed to the repo (small PNGs).

## Acceptance criteria

- First run captures baselines; subsequent runs reuse them.

## Tests required

- `tests/unit/modules/visual/test_baseline_storage.py`.

## PRD / CLAUDE.md references

- PRD §10.6.
- CLAUDE.md §29.

## Definition of Done

- [ ] Storage path + metadata.
- [ ] `STATUS.md` updated.
