# Task 14.01 — Score model

## Deliverables

- `engine/scoring/model.py` implementing:
  - Per-component score in [0,100]: each module produces a normalized score.
  - Weighted average using `policy.weights` (defaults from PRD §19.1).
  - Severity penalties applied per CLAUDE §25 ranges:
    - High: −10 to −25 (configurable midpoint).
    - Medium: −3 to −10.
    - Low: −1 to −3.
    - Info: 0.
  - Flake-risk component derived from `runner` metrics (flake_rate, retries).
- Deterministic float rounding (round half to even, 2 decimals).
- Output type `QualityScore` (Phase 01).

## Tests required

- `tests/unit/scoring/test_score_model.py` — exhaustive cases.

## PRD / CLAUDE.md references

- PRD §19.
- CLAUDE.md §25.

## Definition of Done

- [ ] Model implemented and tested.
- [ ] `STATUS.md` updated.
