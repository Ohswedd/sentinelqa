# Task 19.12 — "Coming soon" placeholders in flows

## Deliverables

- Scan rendered DOM for placeholder text patterns: "coming soon", "TBD", "TODO", "lorem ipsum", "feature not implemented", "placeholder", "{placeholder}", "{{placeholder}}".
- Severity: low when text is on a marketing page; medium when within an authenticated flow; high when within a P0 flow (e.g. checkout).

## Acceptance criteria

- Fixture with "Coming soon" inside checkout step triggers high finding.

## Tests required

- `tests/integration/modules/llm_audit/test_coming_soon.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check + severity matrix + tests.
- [ ] `STATUS.md` updated.
