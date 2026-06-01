# ADR-0032: Docs site built with Astro Starlight

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

Phase 27 requires a documentation site at `apps/docs/` that builds in
CI and renders user-facing guides, the CLI/SDK/MCP reference, an ADR
index, and an auto-generated error-codes page. The phase task spec offers two choices —
**Astro Starlight** or **MkDocs Material** — and asks for the choice
to be recorded in an ADR.

The pre-existing monorepo already runs a pnpm workspace, ships several
TypeScript packages, and the phase 27 acceptance criterion is literally
`pnpm --filter @sentinelqa/docs build` writing static HTML to
`apps/docs/dist/`. The auto-generated content (CLI reference, SDK
reference from `api-snapshot.json`, MCP tool list, error codes) is
sourced from Python — emitted as plain Markdown into the docs content
tree by deterministic generators under `scripts/docs/`.

## Decision

Use **Astro Starlight 0.30** for `apps/docs/`. The site lives as a
pnpm workspace member (`@sentinelqa/docs`) with `astro` and
`@astrojs/starlight` as the only runtime deps and `@astrojs/check` +
`typescript` for the typecheck script.

Auto-generated pages (CLI reference, SDK reference, MCP reference,
error codes, ADR index) are written into `apps/docs/src/content/docs/`
by Python generators under `scripts/docs/` — they are committed to git
and the freshness gate (`tests/integration/docs/test_generated_docs_fresh.py`)
fails CI if any of them is stale.

A custom Starlight component override (`src/overrides/PageFrame.astro`)
renders a status badge for every page whose frontmatter declares one
of `Planned | Experimental | Stable | Deprecated` (our engineering rules
docs/dev/status-labels.md). A Python test enforces that every feature
page carries a status.

## Consequences

- **Positive:** matches the existing pnpm workspace tooling, satisfies the literal `pnpm --filter` acceptance criterion, gives us first- class custom components (StatusBadge), and produces a fully static site with no runtime server.
- **Positive:** Markdown content is portable. Generators emit `.md` files that render in GitHub too, so the docs degrade gracefully if someone reads them outside the built site.
- **Negative / trade-off:** Astro adds a non-trivial Node toolchain. Mitigated by pinning exact versions of `astro` and `@astrojs/starlight` and by relying on the existing pnpm cache in CI.
- **Negative / trade-off:** SDK auto-gen has to be done with Python generators rather than `mkdocstrings`. Mitigated — we already lock the public surface in `packages/python-sdk/api-snapshot.json`, so the generator is a trivial JSON → Markdown render.
- **Follow-up obligations:** add an `apps/docs build` step to `.github/workflows/ci.yml`; ensure the freshness gate is wired before Phase 29 final-hardening; add the docs URL to `README.md` once a public hosting target is chosen (out of scope for Phase 27).

## Alternatives considered

- **MkDocs Material with mkdocstrings.** Python-native and would make SDK auto-gen trivially easy. Rejected because the acceptance criterion is `pnpm --filter @sentinelqa/docs build` — wrapping MkDocs in a pnpm `build` script would add a Node↔Python bridge for no real benefit, and we lose the Starlight component model.
- **Docusaurus.** Heavier React tree, larger node_modules, more custom config to get the same sidebar shape. Rejected on weight.
- **Hand-rolled static site (e.g. `pandoc` over `docs/`).** Cheaper to bootstrap but immediately costly to maintain (search, theming, responsive nav, dark mode). Rejected.

## References

- our product spec Differentiation
- our engineering rules
-
- docs/dev/status-labels.md
- Related ADRs: ADR-0021 (SDK surface lockdown), ADR-0023 (MCP server)
