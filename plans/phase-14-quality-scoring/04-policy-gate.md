# Task 14.04 — Policy gate

## Deliverables

- `engine/scoring/policy_gate.py` integrating score + decision + config policy → final exit code via `engine/policy/exit_codes.py`.
- Lifecycle step 14 (`apply_quality_gates`) wired to call this.
- Decision recorded in `score.json` + run summary.

## Acceptance criteria

- Score 86 + no blockers + `min=85` → `pass`, exit 0.
- Score 84 + no blockers + `min=85` → `blocked`, exit 1.
- Critical finding always → `blocked`.

## Tests required

- `tests/unit/scoring/test_policy_gate.py`.

## PRD / CLAUDE.md references

- PRD §19.4 Policy examples.
- CLAUDE.md §25, §39.

## Definition of Done

- [ ] Gate logic implemented and integrated.
- [ ] `STATUS.md` updated.
