# apps/

User-facing applications. our product spec2.

- `cli/` — the `sentinel` Typer CLI.
- `docs/` — docs site source.
- `dashboard/` — optional web dashboard (post-launch; our product spec2).

Apps consume the engine and modules through stable interfaces. They MUST NOT contain core business logic — see our engineering rules and §19.
