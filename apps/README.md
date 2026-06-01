# apps/

User-facing applications. our product spec2.

- `cli/` — the `sentinel` Typer CLI .
- `docs/` — docs site source (Phase 27).
- `dashboard/` — optional web dashboard (post-MVP; our product spec2).

Apps consume the engine and modules through stable interfaces. They MUST NOT contain core business logic — see our engineering rules and §19.
