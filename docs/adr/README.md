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

| ID                                                        | Title                                                                                                          | Status     | Phase |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------- | ----- |
| [0001](./0001-repository-structure.md)                    | Repository structure                                                                                           | `Accepted` | 00    |
| [0002](./0002-language-strategy.md)                       | Language strategy (Python + TypeScript)                                                                        | `Accepted` | 00    |
| [0003](./0003-package-managers.md)                        | Package managers (uv + pnpm)                                                                                   | `Accepted` | 00    |
| [0004](./0004-conventional-commits-and-no-ai-coauthor.md) | Conventional Commits + no-AI-coauthor enforcement                                                              | `Accepted` | 00    |
| [0005](./0005-config-schema.md)                           | Config schema and loader                                                                                       | `Accepted` | 01    |
| [0006](./0006-safety-policy.md)                           | Safety policy and target allowlist                                                                             | `Accepted` | 01    |
| [0007](./0007-run-lifecycle.md)                           | Run lifecycle                                                                                                  | `Accepted` | 02    |
| [0008](./0008-report-schemas-and-reporter.md)             | Report schemas and reporter pipeline                                                                           | `Accepted` | 03    |
| [0009](./0009-python-ts-protocol.md)                      | Python ↔ TypeScript JSONL protocol                                                                            | `Accepted` | 04    |
| [0010](./0010-discovery-mvp-http-first.md)                | Discovery MVP is HTTP-first; Playwright SPA crawl lands in Phase 17                                            | `Accepted` | 05    |
| [0011](./0011-planner-deterministic-vs-llm.md)            | Planner is deterministic-first; LLM adapter opt-in behind a locked, versioned prompt                           | `Accepted` | 06    |
| [0012](./0012-generated-test-conventions.md)              | Generated test conventions (Jinja2 templates, banner safety, TS-owned audit)                                   | `Accepted` | 07    |
| [0013](./0013-runner-architecture.md)                     | Runner architecture (local + Docker, retry, quarantine, sharding)                                              | `Accepted` | 08    |
| [0014](./0014-analyzer-rules.md)                          | Analyzer rules (categorization, root cause, repro, retry, optional LLM)                                        | `Accepted` | 09    |
| [0015](./0015-module-contract-and-functional-module.md)   | Module contract + functional module (CLAUDE §9 lifecycle + `sentinel functional`)                              | `Accepted` | 10    |
| [0016](./0016-accessibility-module.md)                    | Accessibility module — axe-core + deterministic checks (`sentinel a11y`)                                       | `Accepted` | 11    |
| [0017](./0017-performance-module.md)                      | Performance module — synthetic page/API/CPU/leak budgets (`sentinel perf`)                                     | `Accepted` | 12    |
| [0018](./0018-security-module.md)                         | Security module — safe HTTP checks, gated probes, dep + SAST adapters (`sentinel security`)                    | `Accepted` | 13    |
| [0019](./0019-quality-scoring.md)                         | Quality scoring — reproducible 0..100 score + policy gate (`sentinel report --explain-score`)                  | `Accepted` | 14    |
| [0020](./0020-html-pr-and-slack-reports.md)               | HTML, PR-comment, Slack, and trends reports (`sentinel report` re-render)                                      | `Accepted` | 15    |
| [0021](./0021-public-sdk-surface.md)                      | Public SDK surface — `sentinelqa` / `sentinelqa.errors` / `sentinelqa.agent` + snapshot gate                   | `Accepted` | 16    |
| [0022](./0022-ci-integration.md)                          | CI integration — modes, diff-aware selection, posters, Action                                                  | `Accepted` | 17    |
| [0023](./0023-mcp-agent-interface.md)                     | MCP & agent interface — stdlib JSON-RPC server, twelve sentinel.\* tools, envelope contract                    | `Accepted` | 18    |
| [0024](./0024-llm-code-audit-module.md)                   | LLM-Code audit module — heuristics, signal contract, report differentiator                                     | `Accepted` | 19    |
| [0025](./0025-healer-self-repair.md)                      | Healer / self-repair — deterministic proposals, banner-aware apply, assertion-weakening guard                  | `Accepted` | 20    |
| [0026](./0026-visual-regression-module.md)                | Visual regression — Pillow diff, signal-side capture, hard CI-acceptance guard                                 | `Accepted` | 21    |
| [0027](./0027-api-testing-module.md)                      | API testing module — Python `httpx` with layered no-fuzz guards + perf-dedup latency                           | `Accepted` | 22    |
| [0028](./0028-chaos-module.md)                            | Chaos module — Playwright-injected scenarios with JSONL bridge + bounded scenario catalog                      | `Accepted` | 23    |
| [0029](./0029-plugin-architecture.md)                     | Plugin architecture — entry-point discovery, capability/permission declarations, sandbox                       | `Accepted` | 24    |
| [0030](./0030-integrations.md)                            | Integrations — stdlib HTTP adapters, off-by-default, redacted                                                  | `Accepted` | 25    |
| [0031](./0031-example-apps.md)                            | Example apps — self-contained reference implementations + structural CI tests                                  | `Accepted` | 26    |
| [0032](./0032-docs-site.md)                               | Docs site built with Astro Starlight                                                                           | `Accepted` | 27    |
| [0033](./0033-cloud-boundary.md)                          | Cloud boundary — no SentinelQA cloud in the MVP                                                                | `Accepted` | 27    |
| [0034](./0034-python-cli-typescript-runtime.md)           | Python-first CLI with a TypeScript Playwright runtime (PRD §31 Q1)                                             | `Accepted` | 27    |
| [0035](./0035-generated-tests-in-user-repo.md)            | Generated tests live in the user's repo (PRD §31 Q2)                                                           | `Accepted` | 27    |
| [0036](./0036-cloud-delayed-until-cli-traction.md)        | Cloud is delayed until the CLI earns adoption (PRD §31 Q3)                                                     | `Accepted` | 27    |
| [0037](./0037-llm-provider-agnostic.md)                   | Provider-agnostic LLM access through adapters (PRD §31 Q4)                                                     | `Accepted` | 27    |
| [0038](./0038-mcp-day-one.md)                             | Ship an MCP server on day one (PRD §31 Q5)                                                                     | `Accepted` | 27    |
| [0039](./0039-planner-deterministic-llm-split.md)         | Discovery + execution deterministic, planning LLM-augmented (PRD §31 Q6)                                       | `Accepted` | 27    |
| [0040](./0040-visual-built-in-first.md)                   | Built-in visual diff engine first, integrations later (PRD §31 Q7)                                             | `Accepted` | 27    |
| [0041](./0041-framework-agnostic-with-nextjs.md)          | Framework-agnostic crawler with first-class Next.js support (PRD §31 Q8)                                       | `Accepted` | 27    |
| [0042](./0042-multi-provider-llm-adapter.md)              | Multi-provider LLM adapter layer (Anthropic, OpenAI, Gemini, Ollama, Azure, Vertex, Mistral, Groq, OpenRouter) | `Accepted` | 30    |
| [0043](./0043-browser-authenticated-audits.md)            | Browser-authenticated audits via an encrypted Playwright `storage_state` vault                                 | `Accepted` | 31    |
| [0044](./0044-extended-security-skill-catalog.md)         | Extended security skill catalog (JWT, TLS, GraphQL, BOLA/BFLA, SSRF, bundle secrets, CWE/ATT&CK mapping)       | `Accepted` | 32    |
| [0045](./0045-supply-chain-module.md)                     | Supply-Chain & Dependency Audit (CycloneDX SBOM, OSV lookup, freshness, postinstall, container, SPDX licenses) | `Accepted` | 33    |
| [0046](./0046-compliance-packs.md)                        | Compliance Packs (WCAG 2.2 AA, GDPR baseline, CCPA baseline, SOC 2 trail) + pack DSL + `Finding.compliance_id` | `Accepted` | 34    |
