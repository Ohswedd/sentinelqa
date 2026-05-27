# Task 09.02 — Root cause hypothesis

## Objective

For each categorized failure, produce a short root-cause hypothesis with confidence and supporting evidence pointers.

## Deliverables

- `engine/analyzer/root_cause.py` with `hypothesize(failure, run_context) -> RootCauseHypothesis` returning:
  - `category` (from 09.01).
  - `hypothesis` (1–2 sentences, no jargon).
  - `confidence` (0–1).
  - `evidence_refs` (list of evidence paths or JSONL event seqs).
  - `next_actions` (small ordered list: "open <trace.zip> in Playwright", "check <route> response in <har>").
- Hypothesis templates per category — readable, actionable, never blame-y.

## Steps

1. Author the templates per category.
2. Connect to evidence aggregator to pull the right artifacts.
3. Add tests.

## Acceptance criteria

- A locator-timeout failure produces hypothesis like "Element with accessible name 'Sign in' was not found within 30s. Likely cause: button renamed, removed, or rendered conditionally after auth state changed."
- Confidence reasonable (not always 1.0).

## Tests required

- `tests/unit/analyzer/test_root_cause.py`.

## PRD / CLAUDE.md references

- PRD §9.5.
- CLAUDE.md §9, §24.

## Definition of Done

- [ ] Hypotheses for each category covered by tests.
- [ ] `STATUS.md` updated.
