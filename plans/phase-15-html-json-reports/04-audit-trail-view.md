# Task 15.04 — Audit trail view

## Deliverables

- The HTML report includes a collapsible "Audit trail" section rendering the redacted `audit.log` chronologically:
  - Safety decisions.
  - Module start/end.
  - Policy gate decision.
  - Reporter artifact emissions.
- Provides a small filter (level, module).

## Acceptance criteria

- Audit section renders for the fixture run.
- No secrets visible.

## Tests required

- `tests/integration/reporter/test_audit_view.py`.

## PRD / CLAUDE.md references

- PRD §20.
- CLAUDE.md §11, §33.

## Definition of Done

- [ ] Audit view present + redacted.
- [ ] `STATUS.md` updated.
