---
title: 'SentinelQA — PRD Coverage Matrix'
date: 2026-05-30
auditor: ohswedd
phase: 29 (Final Hardening & PRD Reconciliation)
status: PASS
---

# SentinelQA — PRD Coverage Matrix (Phase 29.06)

This matrix walks **every numbered subsection** of `PRD.md` and pins it to
either (a) the phase / task that implemented it or (b) the ADR that
documents why it is deferred / out of scope. A blank row is a blocker for
closing Phase 29.

| PRD section | Title                                   | Verdict                                                                                                                  |
| ----------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| §0          | Executive Summary                       | Vision only — no implementation surface.                                                                                 |
| §1.1        | Current market status                   | Documented in `docs/dev/competitive-landscape.md` (Phase 27); no code.                                                   |
| §1.2        | Key conclusion                          | Same as §1.1.                                                                                                            |
| §2          | Safety & Legal Boundary                 | Implemented in Phase 01 (`engine/safety/policy.py`); audited in Phase 29.01 (`docs/release/safety-audit-2026-05-30.md`). |
| §2.1        | Forbidden capabilities                  | Implemented in Phase 01 (`engine/policy/forbidden_features.py`); tests under `tests/security/`.                          |
| §2.2        | Allowed alternative: compliant realism  | Implemented in Phase 01 + Phase 05 (transparent UA, `X-SentinelQA-Test-Run`, rate limits).                               |
| §2.3        | Security testing policy                 | Implemented in Phase 13 (`modules/security/`); allowlist enforcement re-audited Phase 29.01.                             |
| §3.1        | Vision statement                        | Documented; no code.                                                                                                     |
| §3.2        | Product mission                         | Documented; no code.                                                                                                     |
| §3.3        | Strategic wedge                         | Documented; reflected in the Phase 19 LLM-audit module + Phase 16 SDK + Phase 18 MCP.                                    |
| §4.1        | Solo AI builder persona                 | Reflected in the docs site IA (Phase 27) and the CLI ergonomics (Phase 02).                                              |
| §4.2        | Startup engineer persona                | Same.                                                                                                                    |
| §4.3        | QA engineer persona                     | Same.                                                                                                                    |
| §4.4        | Engineering manager persona             | Reflected in the HTML report + PR comment (Phase 15).                                                                    |
| §4.5        | AI coding agent persona                 | Implemented in Phase 18 (MCP server + agent-message protocol).                                                           |
| §5          | Core Jobs To Be Done                    | Implemented across Phases 02–25; each JTBD maps to a CLI command.                                                        |
| §6          | Product Principles                      | Enforced repo-wide; Phase 29.07 (CLAUDE.md coverage) ties each principle to a test.                                      |
| §7.1        | In scope (MVP)                          | Phases 00–17 collectively constitute the MVP (per `plans/README.md` §5).                                                 |
| §7.2        | Out of scope for MVP                    | ADR-0033 (cloud boundary), ADR-0036 (cloud delayed).                                                                     |
| §7.3        | Future scope                            | Documented in `docs/release/pre-1.0-review.md` + ADR-0033. Not in this 30-phase plan; not deferred scope.                |
| §8.1        | Competitor matrix                       | `docs/dev/competitive-landscape.md` (Phase 27).                                                                          |
| §8.2        | Is someone already doing this?          | Same.                                                                                                                    |
| §9.1        | Discovery module                        | Phase 05 (`engine/discovery/`); §9.1.1 MVP delivery row added in Phase 05.                                               |
| §9.2        | Planner module                          | Phase 06 (`engine/planner/`); §9.2.1 MVP delivery row added in Phase 06.                                                 |
| §9.3        | Generator module                        | Phase 07 (`engine/generator/`); §9.3.1 MVP delivery row added in Phase 07.                                               |
| §9.4        | Runner module                           | Phase 08 (`engine/runner/`); §9.4.1 MVP delivery row added in Phase 08.                                                  |
| §9.5        | Analyzer module                         | Phase 09 (`engine/analyzer/`); §9.5.1 MVP delivery row added in Phase 09.                                                |
| §9.6        | Healer module                           | Phase 20 (`engine/healer/`); ADR-0025.                                                                                   |
| §9.7        | Reporter module                         | Phase 03 (schemas + writers) + Phase 15 (HTML/PR/Slack); ADR-0008, ADR-0020.                                             |
| §10.1       | Functional E2E testing                  | Phase 10 (`modules/functional/`); §10.1.1 MVP delivery row added in Phase 10.                                            |
| §10.2       | Regression testing                      | Phase 17 (CI lanes, baseline snapshots in PR comments).                                                                  |
| §10.3       | API testing                             | Phase 22 (`modules/api/`); ADR-0027.                                                                                     |
| §10.4       | Accessibility testing                   | Phase 11 (`modules/accessibility/`); §10.4.1 MVP delivery row added in Phase 11; ADR-0016.                               |
| §10.5       | Performance testing                     | Phase 12 (`modules/performance/`); ADR-0017.                                                                             |
| §10.6       | Visual testing                          | Phase 21 (`modules/visual/`); ADR-0026, ADR-0040.                                                                        |
| §10.7       | Security testing                        | Phase 13 (`modules/security/`); ADR-0018.                                                                                |
| §10.8       | Chaos / adversarial testing             | Phase 23 (`modules/chaos/`); ADR-0028.                                                                                   |
| §10.9       | LLM-code-specific audits                | Phase 19 (`modules/llm_audit/`); ADR-0024.                                                                               |
| §11.1       | High-level architecture                 | Phase 00 (repo layout) + Phase 04 (TS runtime) + Phase 24 (plugins); ADR-0001, ADR-0034.                                 |
| §11.2       | Repository structure                    | Phase 00; PRD §11.2 tree extended in Phase 26.                                                                           |
| §11.2.1     | Example apps (Phase 26 delivery)        | Phase 26 (`examples/`); ADR-0031.                                                                                        |
| §11.3       | Language strategy                       | ADR-0002 (Python + TypeScript), ADR-0034 (Python CLI + TS runtime).                                                      |
| §12.1       | First-time setup                        | Phase 02 (`sentinel init` + `sentinel doctor`).                                                                          |
| §12.2       | Local app audit                         | Phase 02 + every module phase.                                                                                           |
| §12.3       | PR diff audit                           | Phase 17 (GitHub Action).                                                                                                |
| §12.4       | Test generation workflow                | Phase 07 (`sentinel generate`).                                                                                          |
| §12.5       | Failure repair workflow                 | Phase 20 (`sentinel fix`).                                                                                               |
| §12.6       | Safe security audit workflow            | Phase 13 (`sentinel security`).                                                                                          |
| §12.7       | LLM agent workflow                      | Phase 18 (MCP `sentinel.*` tools); ADR-0023, ADR-0038.                                                                   |
| §13.1       | CLI commands                            | Phase 02 (skeleton) + each module phase wires its subcommand.                                                            |
| §13.2       | Exit codes                              | Phase 01 (`engine/errors/codes.py`); PRD §13.2 corrected to the canonical 8-code grid in Phase 01.                       |
| §13.3       | Example commands                        | Phase 02 + module phases (covered by CLI integration tests).                                                             |
| §14.1       | SDK basic usage                         | Phase 16 (`packages/python-sdk/`).                                                                                       |
| §14.2       | SDK agent-friendly usage                | Phase 16 (`to_agent_message()` on every public entity).                                                                  |
| §14.3       | SDK classes                             | Phase 16; ADR-0021.                                                                                                      |
| §14.4       | SDK requirements                        | Phase 16 (`packages/python-sdk/api-snapshot.json` is the public contract; CI gates drift).                               |
| §14.5       | SDK MVP delivery (Phase 16)             | Phase 16.                                                                                                                |
| §15.1       | TS runtime purpose                      | Phase 04 (`packages/ts-runtime/`).                                                                                       |
| §15.2       | TS runtime example helper               | Phase 04 (`src/helpers.ts`).                                                                                             |
| §15.3       | `sentinel-ts` binary contract           | Phase 04 (`src/cli.ts`); ADR-0009.                                                                                       |
| §15.4       | JSONL event protocol                    | Phase 04 (`packages/shared-schema/ts-events.schema.json` + `engine/orchestrator/ts_bridge.py`).                          |
| §15.5       | Evidence capture defaults               | Phase 04 (`SENTINEL_PLAYWRIGHT_DEFAULTS`).                                                                               |
| §15.6       | Semantic locator strategy               | Phase 04 (`src/locators.ts`) + Phase 07 (audit-locators).                                                                |
| §15.7       | Safety boundary + redaction symmetry    | Phase 04 + Phase 13 (parity tests).                                                                                      |
| §16.1       | MCP tools                               | Phase 18 (`packages/mcp-server/`).                                                                                       |
| §16.2       | MCP example request                     | Phase 18 (integration tests).                                                                                            |
| §16.3       | MCP example response                    | Phase 18.                                                                                                                |
| §16.4       | MCP MVP delivery (Phase 18)             | Phase 18.                                                                                                                |
| §17.1       | `sentinel.config.yaml`                  | Phase 01 (`engine/config/`); ADR-0005.                                                                                   |
| §18.1       | Core entities                           | Phase 01 (`engine/domain/`); `make schemas` writes 17 stable `*.schema.json`.                                            |
| §18.2       | Finding schema                          | Phase 01 + Phase 03 (`findings.schema.json`).                                                                            |
| §19.1       | Score components                        | Phase 14 (`engine/scoring/`); ADR-0019.                                                                                  |
| §19.2       | Severity penalties                      | Phase 14.                                                                                                                |
| §19.3       | Release decisions                       | Phase 14.                                                                                                                |
| §19.4       | Policy examples                         | Phase 14 (`sentinel.config.yaml.example`).                                                                               |
| §19.5       | Scoring MVP delivery (Phase 14)         | Phase 14.                                                                                                                |
| §20.1       | Persisted artifacts                     | Phase 03 (run.json/findings.json/score.json/junit/sarif/html/md).                                                        |
| §20.2       | Finding evidence requirement            | Phase 03 (`findings_linter.py` blocks evidence-less ≥medium).                                                            |
| §20.3       | Schema drift guard                      | Phase 03 (`tests/integration/reporter/test_schemas_are_valid.py`).                                                       |
| §21.1       | GitHub Action                           | Phase 17 (`sentinel init` ships this byte-equal).                                                                        |
| §21.2       | PR comment                              | Phase 15 (`engine/reporter/pr_comment.py`).                                                                              |
| §21.3       | CI modes                                | Phase 17.                                                                                                                |
| §21.4       | CI MVP delivery (Phase 17)              | Phase 17.                                                                                                                |
| §21.5       | Phase 25 integrations                   | Phase 25 (`integrations/`); ADR-0030.                                                                                    |
| §22.1       | Plugin types                            | Phase 24 (`engine/plugins/`); ADR-0029.                                                                                  |
| §22.2       | Plugin interface                        | Phase 24 (`engine/plugins/manifest.py`).                                                                                 |
| §22.3       | Plugin requirements                     | Phase 24 (`plugin-manifest.schema.json`).                                                                                |
| §22.4       | Plugin MVP delivery (Phase 24)          | Phase 24.                                                                                                                |
| §23.1       | SentinelQA as a security-sensitive tool | Phase 01 + Phase 13 + Phase 29.01.                                                                                       |
| §23.2       | Abuse prevention                        | Phase 01 (allowlist) + Phase 24 (plugin capability rejection) + Phase 29.01 audit.                                       |
| §24.1       | MVP goals                               | Phases 00–17 (`plans/README.md` §5).                                                                                     |
| §24.2       | MVP features                            | Phases 00–17 (per-phase READMEs).                                                                                        |
| §25         | Engineering Milestones                  | Reflected one-to-one in `plans/README.md` §2.                                                                            |
| §26.1       | CLI skeleton                            | Phase 02.                                                                                                                |
| §26.2       | Runner interface                        | Phase 08.                                                                                                                |
| §26.3       | Module interface                        | Phase 10 (`engine.modules.base.SentinelModule`); ADR-0015.                                                               |
| §27         | Example Generated Playwright Test       | Phase 07 (`engine/generator/templates/`) + Phase 26 (`examples/`).                                                       |
| §28.1       | Differentiation — Do not claim          | Phase 27 docs site + Phase 28 messaging review.                                                                          |
| §28.2       | Differentiation — Claim                 | Same.                                                                                                                    |
| §28.3       | Messaging                               | `docs/dev/positioning.md` (Phase 27); ADR-0037, ADR-0041.                                                                |
| §29.1       | Product risks                           | Phase 27 docs + Phase 29 audits.                                                                                         |
| §29.2       | Technical risks                         | Phase 27 docs + Phase 29 audits.                                                                                         |
| §29.3       | Mitigations                             | Phase 27 docs + Phase 29 audits.                                                                                         |
| §30.1       | Developer metrics                       | Phase 27 docs.                                                                                                           |
| §30.2       | QA metrics                              | Phase 27 docs.                                                                                                           |
| §30.3       | Business metrics                        | Phase 27 docs.                                                                                                           |
| §31         | Open Questions                          | Phase 27 (each open question resolved via an ADR in the 0033–0041 range).                                                |
| §31.1       | Resolutions (Phase 27)                  | Phase 27 (ADRs 0033–0041 + ADR README rollup).                                                                           |
| §32         | Recommended Build Order                 | Reflected in `plans/README.md` §2 ordering.                                                                              |
| §33         | Reference Sources                       | Preserved in `docs/dev/references.md` (Phase 27).                                                                        |
| §34         | Final Verdict                           | Phase 29 — this audit + the gate-review row in `STATUS.md`.                                                              |

## Verdict

No blank rows. Every PRD subsection has a recorded landing place — either a
phase that implemented it, an ADR that explains why it is deferred /
out-of-scope, or an explicit "vision only" tag for §0 / persona / §28
prose. Phase 29.06 closes **PASS**.

— ohswedd, 2026-05-30
