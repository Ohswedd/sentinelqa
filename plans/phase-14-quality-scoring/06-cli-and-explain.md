# Task 14.06 — `sentinel report --explain-score`

## Deliverables

- A subcommand `sentinel report --explain-score <run-id>` (or `--latest`) prints the score breakdown:
  - Component scores with raw inputs.
  - Weights applied.
  - Severity penalties summary.
  - Blockers with justifications.
  - Final decision.
- Also produces a Markdown explanation under `<run-dir>/score-explanation.md`.

## Acceptance criteria

- Explanation matches `score.json` numbers exactly.

## Tests required

- `tests/integration/cli/test_explain_score.py`.

## PRD / CLAUDE.md references

- PRD §19.
- CLAUDE.md §25, §38.

## Definition of Done

- [ ] Command works; explanation matches data.
- [ ] `STATUS.md` updated.
