# Task 09.04 — Retry / quarantine decision

## Objective

Decide whether each failure should be retried (passing analyzer's flake heuristic) or flagged for human review.

## Deliverables

- `engine/analyzer/retry_decision.py` exposing `should_retry(failure, history?) -> RetryDecision` returning:
  - `decision` (`retry` | `quarantine_candidate` | `no_action`).
  - `reason`.
  - `confidence`.
- Heuristics:
  - Network error → retry.
  - Browser crash → retry once.
  - Locator-timeout with consistent app behavior across attempts → no retry; suggest quarantine candidate if app is otherwise healthy.
  - App bug (real 5xx) → no retry.
  - Flake history (if prior runs available) → adjust confidence.

## Steps

1. Implement decision rules.
2. Plumb decisions back into the runner for the next loop (Phase 08 retry policy reads these).
3. Tests.

## Acceptance criteria

- Decisions match expectations on fixture cases.

## Tests required

- `tests/unit/analyzer/test_retry_decision.py`.

## PRD / CLAUDE.md references

- PRD §9.5.
- CLAUDE.md §9, §23.

## Definition of Done

- [ ] Decisions deterministic and tested.
- [ ] `STATUS.md` updated.
