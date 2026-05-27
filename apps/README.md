# apps/

User-facing applications. PRD §11.2.

- `cli/` — the `sentinel` Typer CLI (PRD §13, lands in Phase 02).
- `docs/` — docs site source (Phase 27).
- `dashboard/` — optional web dashboard (post-MVP; PRD §11.2).

Apps consume the engine and modules through stable interfaces. They MUST NOT contain core business logic — see `CLAUDE.md` §7 and §19.
