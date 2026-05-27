# Task 20.07 — `sentinel fix` command

## Deliverables

- Replace Phase 02 stub of `fix`.
- Options: `--latest`, `--run <id>`, `--apply safe|aggressive|none`, `--dry-run`, `--allow-weaken`, `--review-only`.
- Behavior:
  - Reads `healer/*.json` proposals from the run dir.
  - Optionally applies safe ones in place; prints a unified diff for the rest.
  - Re-runs affected tests after applying.

## Tests required

- `tests/integration/cli/test_fix.py`.

## PRD / CLAUDE.md references

- PRD §12.5 Failure repair workflow.
- CLAUDE.md §13, §23.

## Definition of Done

- [ ] CLI command working.
- [ ] `STATUS.md` updated.
