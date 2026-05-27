# Task 29.03 — Determinism audit

## Deliverables

- Run `sentinel audit` against the Next.js example 3 times with identical inputs.
- Compare `findings.json` and `score.json` byte-for-byte.
- Acceptable differences: timestamps, durations, run IDs. Everything else must be identical (CLAUDE §6.8 / §19).
- A diff helper `scripts/diff-runs.py` removes timestamp noise and prints any remaining diff.

## Acceptance criteria

- Runs are deterministic modulo allowed fields.

## Tests required

- `tests/integration/release/test_determinism.py` automates a 3-run comparison.

## Definition of Done

- [ ] Audit script + test green.
- [ ] `STATUS.md` updated.
