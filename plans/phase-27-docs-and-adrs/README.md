# Phase 27 — Docs & ADRs

## Objective

Bring the developer + user documentation to release quality. Make sure every CLAUDE §34 ADR trigger has an ADR. Build a docs site (`apps/docs/`) using a simple, stable generator (Astro Starlight or MkDocs Material). Status-label every feature page.

## PRD / CLAUDE.md references

- PRD §28 Differentiation, §31 Open questions, §33 Reference sources.
- CLAUDE.md §34 Documentation rules.

## Sub-phases & tasks

1. `01-docs-site.md` — Astro Starlight / MkDocs Material scaffold + nav.
2. `02-user-guides.md` — Install, quickstart, CLI reference, SDK reference.
3. `03-status-labels.md` — Apply `Planned`/`Experimental`/`Stable`/`Deprecated` to every feature page.
4. `04-adrs.md` — Ensure every CLAUDE §34 trigger has an Accepted ADR.
5. `05-open-questions.md` — Answer the PRD §31 open questions as ADRs with the recommended answers as defaults.
6. `06-error-codes-reference.md` — Generated from `engine/errors/codes.py`.
7. `07-tests.md` — Link checker, vale prose linter, sample-render in CI.

## Definition of Done

- Docs site builds in CI.
- All §34 ADRs exist.
- All PRD §31 open questions have ADRs.

## Phase Gate Review

- [ ] Docs site renders + linked from README.
- [ ] ADR index complete.
- [ ] Open-question ADRs cover all 8.
- [ ] Error code reference auto-generated.
- [ ] `STATUS.md` updated.
