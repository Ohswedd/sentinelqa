# docs/

Status: `Stable`

Project documentation. PRD §11.2, CLAUDE §34.

## Sub-trees

- [`adr/`](./adr/) — Architecture Decision Records. Mandatory for every trigger in `CLAUDE.md` §34.
- [`dev/`](./dev/) — Contributor docs: local setup, branching, commits, secret hygiene, ownership, CI, status labels, agent workflow.
- [`user/`](./user/) — End-user docs (CLI usage, SDK reference, module catalog). Populated from Phase 27 onward.

## Every doc, one line

### `adr/`

- [`README.md`](./adr/README.md) — what an ADR is, the §34 triggers, the status lifecycle, the index of accepted ADRs.
- [`_template.md`](./adr/_template.md) — canonical headings every ADR must use.
- [`0001-repository-structure.md`](./adr/0001-repository-structure.md) — locks in the PRD §11.2 monorepo layout.
- [`0002-language-strategy.md`](./adr/0002-language-strategy.md) — Python owns CLI/SDK/orchestration; TypeScript owns Playwright runtime.
- [`0003-package-managers.md`](./adr/0003-package-managers.md) — `uv` for Python, `pnpm` for TypeScript; coverage-floor flag day pegged to Phase 01.05.
- [`0004-conventional-commits-and-no-ai-coauthor.md`](./adr/0004-conventional-commits-and-no-ai-coauthor.md) — commitlint enforcement + the AI-coauthor pattern list.

### `dev/`

- [`local-setup.md`](./dev/local-setup.md) — prerequisites, `make install`, troubleshooting.
- [`branching.md`](./dev/branching.md) — branch prefixes, pre-PR checklist.
- [`commits.md`](./dev/commits.md) — Conventional Commits rules and 10 worked examples.
- [`secret-hygiene.md`](./dev/secret-hygiene.md) — `.gitignore` + `.env.example` + gitleaks + redaction rules.
- [`ownership.md`](./dev/ownership.md) — repository visibility, authorship, no-AI-coauthor, package metadata.
- [`trademarks-and-naming.md`](./dev/trademarks-and-naming.md) — placeholder; trademark clearance lands in Phase 28.
- [`ci-and-branch-protection.md`](./dev/ci-and-branch-protection.md) — workflow inventory and required GitHub branch-protection rules.
- [`status-labels.md`](./dev/status-labels.md) — the four documentation status labels (`Planned`, `Experimental`, `Stable`, `Deprecated`).
- [`agent-workflow.md`](./dev/agent-workflow.md) — playbook for LLM coding agents (the `plans/PROMT.md` loop).

### `user/`

Empty in Phase 00. Populated from Phase 27 onward with CLI usage, SDK reference, module catalog, and runbook docs.

## Conventions

Every doc carries a status label from `CLAUDE.md` §34 (`Planned`, `Experimental`, `Stable`, `Deprecated`). See [`dev/status-labels.md`](./dev/status-labels.md).

When a doc references a PRD or CLAUDE.md rule, it cites the section number (e.g. "`CLAUDE.md` §33", "PRD §11.2"). Citations let future contributors trace the source even if line numbers shift.
