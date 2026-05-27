# Architecture Decision Records (ADRs)

Status: `Stable`

Authority: `CLAUDE.md` §34 (Documentation rules). PRD §32 (Recommended Build Order — ADR triggers are implicit in the phase order).

An **ADR** records _why_ a non-obvious architectural choice was made, so the next contributor (human or agent) can extend, supersede, or revisit it with context instead of re-deriving the trade-off from first principles.

## When to write an ADR

`CLAUDE.md` §34 mandates an ADR for any of these triggers:

- **Runtime architecture** — choice or change of an executor, scheduler, queue, or runtime topology.
- **Plugin system** — module/plugin interface contract.
- **Config schema** — top-level shape of `sentinel.config.yaml` and validation rules.
- **Scoring algorithm** — change to how `score.json` is derived from findings.
- **Report schema** — change to any persisted output (`run.json`, `findings.json`, `score.json`, JUnit, SARIF, HTML).
- **Security policy** — change to the safety boundary (`CLAUDE.md` §6 / PRD §2) or to the target allowlist semantics.
- **Agent / MCP design** — change to the `sentinel.*` MCP tool contract or to the agent message protocol.
- **Cloud boundary** — anything that crosses from local to remote execution (BrowserStack, Sauce Labs, cloud orchestrator, etc.).

If you hit any of these triggers in a PR and there is no ADR for the change, the PR is incomplete. Add the ADR first; reference it from the PR description.

## Status lifecycle

| Status                   | Meaning                                                                             |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `Proposed`               | The change is under discussion; no implementation has merged.                       |
| `Accepted`               | The decision is in effect; implementation has merged or is being merged in this PR. |
| `Superseded by ADR-NNNN` | A later ADR has replaced this one. Keep this file for history; do not delete.       |
| `Deprecated`             | The decision still stands historically but should not be applied to new code.       |

Never delete an ADR. Supersede it.

## Filename + numbering

`docs/adr/NNNN-kebab-case-title.md` with `NNNN` zero-padded to four digits. Numbers are assigned in commit order; collisions are resolved by whoever lands second renumbering and updating cross-references.

## Template

Use [`_template.md`](./_template.md). The required headings are validated by `scripts/check-adrs.sh` (wired into `make adr-check` and CI). A PR that adds or modifies an ADR file is rejected if any required heading is missing.

## Index of accepted ADRs

| ID                                                        | Title                                             | Status     | Phase |
| --------------------------------------------------------- | ------------------------------------------------- | ---------- | ----- |
| [0001](./0001-repository-structure.md)                    | Repository structure                              | `Accepted` | 00    |
| [0002](./0002-language-strategy.md)                       | Language strategy (Python + TypeScript)           | `Accepted` | 00    |
| [0003](./0003-package-managers.md)                        | Package managers (uv + pnpm)                      | `Accepted` | 00    |
| [0004](./0004-conventional-commits-and-no-ai-coauthor.md) | Conventional Commits + no-AI-coauthor enforcement | `Accepted` | 00    |
| [0005](./0005-config-schema.md)                           | Config schema and loader                          | `Accepted` | 01    |
| [0006](./0006-safety-policy.md)                           | Safety policy and target allowlist                | `Accepted` | 01    |
| [0007](./0007-run-lifecycle.md)                           | Run lifecycle                                     | `Accepted` | 02    |
| [0008](./0008-report-schemas-and-reporter.md)             | Report schemas and reporter pipeline              | `Accepted` | 03    |
