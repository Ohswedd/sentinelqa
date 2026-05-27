# Task 15.05 — `sentinel report` command

## Deliverables

- Replace Phase 02 stub of `report`.
- Subcommands / flags:
  - `sentinel report --latest` — re-render reports for the latest run.
  - `sentinel report <run-id>` — render for a specific run.
  - `sentinel report --format html,json,sarif,junit,md` — limit output.
  - `sentinel report --explain-score` (covered in Phase 14).
  - `sentinel report --open` — open the HTML in the default browser (skip in CI).
- Idempotent re-render: same inputs → same outputs.

## Tests required

- `tests/integration/cli/test_report.py`.

## PRD / CLAUDE.md references

- PRD §13, §9.7.
- CLAUDE.md §13, §38.

## Definition of Done

- [ ] Report CLI implemented and tested.
- [ ] `STATUS.md` updated.
