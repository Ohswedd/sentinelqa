# Task 07.06 — `sentinel generate` command

## Objective

Wire the generator into the CLI: `sentinel generate --url …` (or `--from-plan <path>`).

## Deliverables

- Replace Phase 02 stub of `generate`.
- Options: `--url`, `--from-plan`, `--out tests/sentinel`, `--source .`, `--force` (overwrite existing generated files), `--dry-run`, `--json`.
- Behavior:
  - Runs lifecycle 1–9 unless `--from-plan` provided.
  - Generates page-objects, fixtures, specs, plan.md.
  - Without `--force`, preserves files with hand-edits (detect by checking for the banner; if missing, file is considered hand-owned).
  - Always runs the brittleness audit.
  - Runs `tsc --noEmit` over the output as a sanity check unless `--no-tsc`.

## Steps

1. Implement the command + option handling.
2. Add the file-overwrite guard.
3. Integration test against fixture.

## Acceptance criteria

- `sentinel generate --url <fixture>` creates working Playwright tests.
- Re-running with the same plan is idempotent.

## Tests required

- `tests/integration/cli/test_generate.py`.

## PRD / CLAUDE.md references

- PRD §13, §12.4 Generation workflow.
- CLAUDE.md §13, §22.

## Definition of Done

- [ ] CLI command implemented and tested.
- [ ] `STATUS.md` updated.
