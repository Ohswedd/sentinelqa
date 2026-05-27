# Task 18.04 — `sentinel.verify_fix` loop

## Deliverables

- `sentinel.verify_fix` accepts a `RepairSuggestion` (test fix or app fix described in code-change form). For app fixes, the tool runs against the current working tree (it does NOT apply code changes — that's the agent's job; SentinelQA only verifies).
- For each call:
  - Re-runs the impacted tests (using diff-aware selection).
  - Reports new findings, fixed findings, and unchanged findings.
  - Returns a structured `VerifyFixResult` with `decision` (`fix_verified`, `partial`, `regressed`, `still_failing`).

## Acceptance criteria

- Fixture loop: agent applies a known fix → `verify_fix` reports `fix_verified` and no new findings.

## Tests required

- `tests/integration/mcp/test_verify_fix_loop.py`.

## PRD / CLAUDE.md references

- PRD §12.7 LLM agent workflow, §16.
- CLAUDE.md §15, §23.

## Definition of Done

- [ ] Verify-fix end-to-end works.
- [ ] `STATUS.md` updated.
