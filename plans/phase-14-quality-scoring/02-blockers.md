# Task 14.02 — Blockers

## Deliverables

- `engine/scoring/blockers.py` exposing `compute_blockers(findings, module_results, policy) -> list[Finding]`.
- Rules per CLAUDE §25:
  - Any `critical` severity → blocker (unless policy explicitly allows).
  - Any `high` severity in `security` module → blocker if `policy.block_on_high_security`.
  - Any failed P0 functional flow → blocker.
  - More than `policy.max_failed_p1_flows` → blocker.
- Each blocker carries: rule_name, finding_id, justification.

## Tests required

- `tests/unit/scoring/test_blockers.py`.

## PRD / CLAUDE.md references

- PRD §19, §10.7.
- CLAUDE.md §25.

## Definition of Done

- [ ] Blocker rules implemented and tested.
- [ ] `STATUS.md` updated.
