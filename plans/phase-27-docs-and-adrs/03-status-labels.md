# Task 27.03 — Status labels

## Deliverables

- Every feature page in the docs has a frontmatter `status:` of one of `Planned`, `Experimental`, `Stable`, `Deprecated`.
- A CI check scans all docs pages for the field; missing → fail.
- A small Astro/MkDocs partial renders the status as a badge at the top of every page.
- **CLI command status surface (Phase-02 carry-over).** PRD §13.1 lists every CLI command in a single code block with no live-vs-stub annotation. By the time Phase 27 runs the doc-site CLI reference must mirror reality. Pull the source of truth from `plans/STATUS.md` (it already tracks which phase ships which command) and either:
  - Render a `| Command | Status | Phase |` table on the CLI reference page (preferred — easy to keep in sync), OR
  - Add status badges next to each command in the CLI reference, generated from the same data.
  PRD §13.1's code block stays untouched (it documents the eventual contract; annotating it would rot every phase). Same approach for PRD §17 sections that reference modules: cross-link to STATUS.md for current implementation state.

## Acceptance criteria

- A page without status fails CI.
- Every shipped module page is `Stable`.
- The CLI reference page accurately reflects which commands are implemented vs. registered-stubs at the time the doc-site is built (sourced from STATUS.md, not hand-curated).

## PRD / CLAUDE.md references

- CLAUDE.md §34.

## Definition of Done

- [ ] Labels applied + CI guard.
- [ ] CLI reference shows per-command status derived from STATUS.md.
- [ ] `STATUS.md` updated.
