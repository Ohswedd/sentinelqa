# Task 14.05 — Reproducibility

## Deliverables

- A property-based test (hypothesis) that:
  - Generates random `Finding` lists + `ModuleResult` lists + policies.
  - Calls scoring twice on the same input.
  - Asserts byte-equal `score.json` outputs.
- A "replay" test: load an existing `findings.json` + config snapshot from a run, recompute, must match `score.json` exactly.

## Acceptance criteria

- Property test green for 5 000 examples.
- Replay test green on 3 canonical runs.

## Tests required

- `tests/property/scoring/test_reproducibility.py`.
- `tests/integration/scoring/test_replay.py`.

## PRD / CLAUDE.md references

- PRD §6.8, §19.
- CLAUDE.md §25.

## Definition of Done

- [ ] Both tests green.
- [ ] `STATUS.md` updated.
