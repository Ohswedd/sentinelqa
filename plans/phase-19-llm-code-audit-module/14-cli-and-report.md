# Task 19.14 — `sentinel llm-audit` command + report section

## Deliverables

- Replace Phase 02 stub of `llm-audit`.
- Options: `--url`, `--config`, `--checks <subset>`, `--ci`, `--json`.
- Report contributions:
  - Dedicated "LLM-Code Audit" section in `report.html` (this is the marketing differentiator).
  - Module summary in PR comment.

## Acceptance criteria

- End-to-end run on `sample-app-llm-broken` fixture lists every triggered check.

## Tests required

- `tests/integration/cli/test_llm_audit.py`.

## PRD / CLAUDE.md references

- PRD §10.9, §28.
- CLAUDE.md §13, §31, §38.

## Definition of Done

- [ ] CLI + report section in place.
- [ ] `STATUS.md` updated.
