# Task 00.07 — ADR framework

## Objective

Set up Architecture Decision Records and capture the initial cross-cutting decisions made in Phase 00. ADRs are mandatory for every trigger listed in `CLAUDE.md` §34.

## Prerequisites

- Tasks 00.01–00.06 complete.

## Deliverables

- `docs/adr/README.md` explaining what an ADR is, when to write one (CLAUDE.md §34 triggers), and the status lifecycle (Proposed → Accepted → Superseded → Deprecated).
- `docs/adr/_template.md` with the canonical headings:
  - `# ADR-NNNN: <title>`
  - `## Status`
  - `## Context`
  - `## Decision`
  - `## Consequences`
  - `## Alternatives considered`
  - `## References` (PRD sections, CLAUDE.md rules, external sources)
- `docs/adr/0001-repository-structure.md` — accepted; locks in PRD §11.2 layout and the Python/TS split.
- `docs/adr/0002-language-strategy.md` — accepted; Python owns CLI/SDK/orchestration; TS owns Playwright runtime (PRD §11.3, §8.3).
- `docs/adr/0003-package-managers.md` — accepted; records the choice of `uv` (or `pip-tools`) for Python and `pnpm` (or `npm`) for TS, with rationale.
- `docs/adr/0004-conventional-commits-and-no-ai-coauthor.md` — accepted; locks in commitlint + the no-AI-coauthor rule from `CLAUDE.md` §3.
- ADR index in `docs/adr/README.md` listing all accepted ADRs.

## Steps

1. Write the template and README.
2. Write each of the four ADRs above. Each ADR must cite the PRD section(s) and CLAUDE.md rule(s) it implements.
3. Add a CI step or a `make` target (`make adr-check`) that fails the build if a newly added file under `docs/adr/` doesn't follow the template (regex over the required headings).

## Acceptance criteria

- All four ADRs marked **Accepted**.
- `make adr-check` passes.
- ADRs reference PRD/CLAUDE.md by section number, not by paraphrase.

## Tests required

- `make adr-check` integration: malform a copy of an ADR, watch it fail, fix it, watch it pass.

## PRD / CLAUDE.md references

- PRD §32 (ADR triggers implicit in the build order).
- CLAUDE.md §34 Documentation rules (ADR triggers list).

## Definition of Done

- [ ] ADR template + README in place.
- [ ] ADR-0001..0004 written and Accepted.
- [ ] `make adr-check` wired into CI.
- [ ] `STATUS.md` updated.
