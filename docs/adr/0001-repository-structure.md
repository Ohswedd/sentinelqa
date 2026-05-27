# ADR-0001: Repository structure

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

SentinelQA spans two runtimes (Python orchestration, TypeScript Playwright runtime), multiple deliverables (CLI, SDK, MCP server, modules, integrations, examples, docs), and a 30-phase execution plan that adds code phase by phase. PRD §11.2 prescribes the exact monorepo layout; CLAUDE.md §7 requires a layered architecture with adapters at the edges. We need a single repository shape that satisfies both before any product code lands.

## Decision

Adopt the monorepo layout in PRD §11.2 verbatim:

```
apps/{cli,docs,dashboard}
packages/{python-sdk,ts-runtime,mcp-server,shared-schema}
engine/{orchestrator,discovery,planner,generator,runner,analyzer,healer,reporter,policy}
modules/{functional,api,accessibility,performance,visual,security,chaos,llm_audit}
integrations/{github,gitlab,browserstack,saucelabs,slack,jira,linear}
examples/{nextjs,fastapi,django,flask,react-vite}
tests/{unit,integration,e2e}
```

Augment it with `docs/{adr,dev,user}/` and `.github/{workflows,ISSUE_TEMPLATE}/` for ADRs, contributor docs, and CI bootstrap (CLAUDE.md §34, §39). Every top-level folder ships a `README.md` citing the PRD section that defines it.

Empty directories are tracked with `.gitkeep` (replaced by real content as each phase ships code into the folder).

## Consequences

- **Positive:** Every PRD §11.2 path is reserved and discoverable from day one. Later phases never have to "create the folder first"; they only add code.
- **Positive:** Layered architecture is enforceable by inspection — code in `engine/` and `modules/` can be lint-/import-checked against framework imports (Typer, FastAPI, Playwright, vendor SDKs), which must live in `apps/` or `integrations/`.
- **Negative / trade-off:** A large empty tree at Phase 00 looks unfinished. Mitigated by per-folder `README.md` files that explain "this is empty on purpose; code lands in Phase NN."
- **Follow-up obligations:** When a `engine/*` or `modules/*` sub-package gains its first `.py` file, it must also gain a `pyproject.toml` and become a `uv` workspace member (see ADR-0003).

## Alternatives considered

- **Flat single-package layout** (everything under one `sentinelqa/` Python package). Rejected: PRD §11.2 explicitly separates `engine/` from `modules/` from `packages/` so plugin boundaries and adapter boundaries are visible in the directory tree.
- **Polyrepo (one repo per package)**. Rejected: cross-cutting changes (e.g. updating the findings schema and every consumer in one PR) would require multi-repo coordination, defeating the "evidence in one place" promise of the product.
- **`src/`-layout at the monorepo root** (a single `src/` covering all packages). Rejected: tooling assumes per-package roots for Python packaging (hatchling builds `packages/python-sdk/src/sentinel`), and a single src layout would force every workspace member to live under one root, breaking the PRD-mandated separation.

## References

- PRD §11.2 Repository structure, §11.3 Language strategy.
- CLAUDE.md §7 Architecture, §43 Implementation Order (item 1).
- Related ADRs: ADR-0002 (language strategy), ADR-0003 (package managers).
