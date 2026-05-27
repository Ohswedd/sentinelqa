# Task 27.03 — Status labels

## Deliverables

- Every feature page in the docs has a frontmatter `status:` of one of `Planned`, `Experimental`, `Stable`, `Deprecated`.
- A CI check scans all docs pages for the field; missing → fail.
- A small Astro/MkDocs partial renders the status as a badge at the top of every page.

## Acceptance criteria

- A page without status fails CI.
- Every shipped module page is `Stable`.

## PRD / CLAUDE.md references

- CLAUDE.md §34.

## Definition of Done

- [ ] Labels applied + CI guard.
- [ ] `STATUS.md` updated.
