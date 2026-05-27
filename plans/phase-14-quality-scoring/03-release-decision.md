# Task 14.03 — Release decision

## Deliverables

- `engine/scoring/decision.py` exposing `decide(score, blockers, run_status) -> PolicyDecision` returning one of:
  - `pass`
  - `pass_with_warnings`
  - `blocked`
  - `inconclusive`
  - `unsafe_target_rejected`
- Rules:
  - `run_status == "unsafe_blocked"` → `unsafe_target_rejected`.
  - `run_status == "incomplete"` → `inconclusive`.
  - Any blocker → `blocked`.
  - Score < `policy.min_quality_score` → `blocked`.
  - Otherwise score >= min and there are any `medium` findings → `pass_with_warnings`.
  - Otherwise → `pass`.

## Tests required

- `tests/unit/scoring/test_decision.py`.

## PRD / CLAUDE.md references

- PRD §19.3.
- CLAUDE.md §25.

## Definition of Done

- [ ] Decision rules implemented and tested.
- [ ] `STATUS.md` updated.
