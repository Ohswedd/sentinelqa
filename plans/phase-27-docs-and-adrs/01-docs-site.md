# Task 27.01 — Docs site scaffold

## Deliverables

- `apps/docs/` set up with **Astro Starlight** (preferred) or MkDocs Material — record choice in a new ADR.
- Nav structure:
  - **Get Started** (install, quickstart, doctor).
  - **Concepts** (architecture, safety boundary, run lifecycle).
  - **CLI Reference** (auto-generated).
  - **SDK Reference** (auto-generated from Python docstrings via `mkdocstrings`/`pdoc`).
  - **MCP Reference** (auto-generated from tool schemas).
  - **Modules** (one page per module).
  - **Plugins** (developer guide).
  - **Integrations** (BrowserStack, Sauce Labs, Slack, GitHub, etc.).
  - **CI/CD**.
  - **ADRs** (linked).
  - **Security & Safety**.
  - **Contributing**.

## Acceptance criteria

- `pnpm --filter @sentinelqa/docs build` produces static HTML in `apps/docs/dist/`.

## Tests required

- CI step builds docs.

## PRD / CLAUDE.md references

- PRD §28.
- CLAUDE.md §34.

## Definition of Done

- [ ] Site scaffold + nav.
- [ ] CI builds.
- [ ] `STATUS.md` updated.
