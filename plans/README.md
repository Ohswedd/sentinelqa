# SentinelQA Implementation Plan

This folder is the **single source of truth for execution**. It decomposes the SentinelQA PRD into 30 phases, each broken into sub-phases and per-task files. Every task is sized so an AI coding agent or human contributor can pick it up, do it, verify it, and commit it without further design work.

> Authority order (per `CLAUDE.md` §2): system safety rules → user instructions → `CLAUDE.md` → `PRD.md` → ADRs → comments → this plan. If this plan contradicts the PRD or CLAUDE.md, the PRD/CLAUDE.md wins — update this plan immediately when you discover the conflict.

---

## 1. How the plan is organized

```
plans/
  README.md                          this file
  STATUS.md                          live progress tracker (update at every phase boundary)
  PROMT.md                           copy/paste prompt that triggers the execution loop
  phase-00-foundation/
    README.md                        phase overview, gates, exit criteria
    01-<task>.md                     detailed task spec
    02-<task>.md
    ...
  phase-01-core-domain-config/
  ...
  phase-29-final-hardening/
```

Each **phase README** contains: objective, PRD/CLAUDE.md references, ordered sub-phases, definition of done, and a checklist of every task file in the folder.

Each **task file** contains: ID, objective, prerequisites (must be done first), inputs, deliverables, step-by-step instructions, acceptance criteria, required tests, PRD/CLAUDE.md citations, and Definition-of-Done checklist.

No task is allowed to be vague. If a task ever feels under-specified, the contributor must refine it in place before starting — leaving the next contributor a sharper spec than they found.

---

## 2. The 30 phases at a glance

| # | Phase | Output |
|---:|---|---|
| 00 | Foundation | Monorepo layout, tooling, CI bootstrap, ADR framework, secret hygiene |
| 01 | Core Domain & Config | Pydantic models for all entities (PRD §18), `sentinel.config.yaml` loader/validator, safety policy, typed exceptions |
| 02 | CLI Skeleton & Run Lifecycle | Typer CLI, `init` / `doctor`, run lifecycle (PRD §10/CLAUDE §10), artifact tree, exit codes, JSON mode |
| 03 | Report Schemas & Reporter | Versioned schemas for `run.json`, `findings.json`, `score.json`, JUnit XML, SARIF, Markdown |
| 04 | TypeScript Playwright Runtime | `@sentinelqa/playwright` helpers, JSONL Python↔TS bridge, trace/screenshot/video capture |
| 05 | Discovery Module | Crawler, DOM map, API endpoint detection, forms inventory, auth boundaries, OpenAPI/GraphQL ingest |
| 06 | Planner Module | Deterministic-first test plan generator, LLM adapter behind interface, P0–P3 priority assignment |
| 07 | Generator Module | Playwright spec/page-object/fixture generator with semantic locators |
| 08 | Runner Module | Local Playwright runner, Docker runner, artifact collection |
| 09 | Analyzer Module | Failure categorization (app vs test vs env vs flake), root cause hypothesis, retry/quarantine logic |
| 10 | Functional Module | Login/signup/CRUD/role/admin/file-upload/payment-sandbox coverage |
| 11 | Accessibility Module | axe-core integration, keyboard/focus/landmark checks, normalized findings |
| 12 | Performance Module | Budgets, LCP/CLS/INP/INP probes, JS bundle size, API latency |
| 13 | Security (Safe) Module | Headers, cookies, CORS, CSRF, safe XSS probe, IDOR smoke, secret scan, SARIF export, allowlist enforcement |
| 14 | Quality Scoring | Reproducible score model, severity penalties, release decision, policy gates |
| 15 | HTML & JSON Reports | Final HTML template, PR comment generator, trend rendering |
| 16 | Python SDK | `Sentinel`, `AuditResult`, `Finding`, `TestPlan`, async support, agent-message serialization |
| 17 | CI Integration | GitHub Action, GitLab CI, PR comment poster, fast/standard/full/nightly/release modes |
| 18 | MCP & Agent Interface | MCP server, 12 sentinel.* tools (PRD §16), agent message protocol |
| 19 | LLM-Code Audit Module | Dead buttons, fake routes, mock-data shipped, missing CRUD edges, frontend-only auth, hardcoded creds |
| 20 | Healer / Self-Repair | Locator repair with confidence, repair proposal schema, human-review gating, `fix` CLI |
| 21 | Visual Regression | Baselines, diff threshold, dynamic content masking, no CI auto-accept |
| 22 | API Testing | OpenAPI/GraphQL contract validation, negative cases, auth, latency budgets |
| 23 | Chaos Module | Slow network, offline, 500/timeout mocking, session expiry, navigation edge cases |
| 24 | Plugin Architecture | ScannerPlugin interface, discovery, capability/permission declaration, sandboxing |
| 25 | Integrations | BrowserStack, Sauce Labs, Slack, GitHub deeper integration |
| 26 | Example Apps | Next.js, FastAPI, Django, Flask, React-Vite demos |
| 27 | Docs & ADRs | Docs site, status labels, ADRs for every CLAUDE §34 trigger |
| 28 | Versioning & Release Prep | Semver, changelog, package metadata, distribution scripts |
| 29 | Final Hardening & PRD Reconciliation | Safety audit, secret-leak audit, determinism audit, DoD sweep, PRD/CLAUDE.md reconcile |

---

## 3. Execution loop (how to advance through the plan)

1. Read `STATUS.md` and identify the active phase + active sub-phase.
2. Read the phase README and the current task file.
3. Cross-check the task against `PRD.md`, `CLAUDE.md`, and any related ADRs.
4. Execute the task on a dedicated branch (e.g. `feature/phase-05-discovery-crawler`).
5. Run all quality gates (`CLAUDE.md` §17): format, lint, typecheck, unit, integration, CLI smoke, security policy, schema/report tests, docs/PRD updates.
6. Commit with Conventional Commits, no `Co-authored-by` for AI tools (per `CLAUDE.md` §3).
7. Update `STATUS.md` (mark task done, advance pointer).
8. Update `PRD.md` and the relevant ADR whenever behavior, schema, or boundaries changed.
9. At the end of a phase, run the **Phase Gate Review** (every phase README defines its own) AND close the phase out with push → PR → CI-watch → merge to `main`. The PR URL, CI run URL, and merge commit SHA are recorded in `STATUS.md`'s **PR & merge log**. Do not start the next phase until both the gate review and the merge to `main` are complete.

Two hard rules (full text in `PROMT.md`):

- **No deferred scope.** "Risks", "follow-ups", `TODO`s, env-var-gated capabilities, "Phase X will…" — any of these phrasings in an end-of-phase summary mean the phase is not done. Finish the work, re-home it to a real task file in a later phase folder, or remove it from scope with an Accepted ADR. Closing a phase with un-rehomed risks is forbidden.
- **Push → CI → merge is part of closing the phase.** The agent pushes, opens/updates the PR, waits on every required check, fixes failures (up to 3 attempts), merges to `main` with `gh pr merge --squash --delete-branch`, and updates `STATUS.md`. You should never have to run those commands by hand.

The `PROMT.md` file contains the exact prompt to paste back into Claude Code to repeat this loop. After every phase, the assistant **must stop**, present the phase review, and wait for re-prompt.

---

## 4. Non-negotiables (re-read before each task)

- **PRD discipline** (`CLAUDE.md` §5): if behavior, CLI/SDK contract, lifecycle, safety boundary, report schema, data model, or scoring changes — update `PRD.md` in the same branch.
- **Safety boundary** (`CLAUDE.md` §6, PRD §2): no stealth, no CAPTCHA bypass, no evasion, no unauthorized targets, no destructive defaults.
- **No fake completion** (`CLAUDE.md` §37): no hardcoded scores, no empty returns dressed as success, no TODOs without tracked notes.
- **Definition of Done** (`CLAUDE.md` §18): implementation matches PRD, tests exist and pass, types/lint pass, safety reviewed, reports/schemas updated, docs/PRD updated, no secrets, clean `git status`.
- **Evidence over magic** (PRD §6.1): every finding has reproducible evidence.
- **Deterministic where possible** (PRD §6.8): LLMs plan/explain, deterministic runners execute and verify.

---

## 5. Where each PRD section lands

| PRD section | Lives in |
|---|---|
| §0 Executive Summary | (vision; nothing to build) |
| §1 Market Context | (positioning; nothing to build) |
| §2 Safety Boundary | Phase 01 (policy), Phase 13 (security), Phase 29 (audit) |
| §3 Vision / §4 Personas / §5 JTBD / §6 Principles | Drives every phase; explicit citations in each task |
| §7 Scope | Phases 00–29 cover **all in-scope** items; out-of-scope is preserved as ADRs |
| §9 Core Modules | 9.1 Discovery → Phase 05; 9.2 Planner → 06; 9.3 Generator → 07; 9.4 Runner → 08; 9.5 Analyzer → 09; 9.6 Healer → 20; 9.7 Reporter → 03 + 15 |
| §10 Testing Capabilities | 10.1 Functional → Phase 10; 10.2 Regression → 17; 10.3 API → 22; 10.4 A11y → 11; 10.5 Perf → 12; 10.6 Visual → 21; 10.7 Security → 13; 10.8 Chaos → 23; 10.9 LLM Audit → 19 |
| §11 Architecture | Phase 00 (repo) + Phase 04 (runtimes) + Phase 24 (plugins) |
| §12 Workflows | Each workflow has a corresponding CLI command implemented in Phase 02 + module phases |
| §13 CLI | Phase 02 (skeleton) + each module phase wires its own subcommand |
| §14 Python SDK | Phase 16 |
| §15 TS Runtime | Phase 04 |
| §16 MCP Tools | Phase 18 |
| §17 Configuration | Phase 01 |
| §18 Data Model | Phase 01 (entities) + Phase 03 (serialized) |
| §19 Quality Scoring | Phase 14 |
| §20 Evidence & Reporting | Phase 03 + Phase 15 |
| §21 CI/CD | Phase 17 |
| §22 Plugin Architecture | Phase 24 |
| §23 Security/Threat Model | Phases 01, 13, 29 |
| §24 MVP Definition | Phases 00–17 collectively constitute the MVP |
| §25 Engineering Milestones | Mapped one-to-one in the phase table above |
| §26 Implementation Skeleton | Phase 02 + Phase 08 + Phase 24 |
| §27 Example Generated Test | Phase 07 + Phase 26 |
| §28 Differentiation | Phase 27 (docs) |
| §29 Risks / §30 Metrics | Phase 27 docs + Phase 29 final review |
| §31 Open Questions | Each answer is captured as an ADR in Phase 27 (with the PRD's recommended answers as the default) |
| §32 Recommended Build Order | Reflected in phase ordering |
| §33 Reference Sources | Preserved in Phase 27 docs |
| §34 Final Verdict | Phase 29 ensures we hold the line |

If a PRD bullet is not visibly accounted for in the phase that should own it, that is a planning bug — fix it in this README and the relevant phase.

---

## 6. Naming, branching, and commit rules (quick reference)

- Branches: `feature/<phase>-<short-slug>`, `fix/<scope>`, `docs/<scope>`, `refactor/<scope>`, `security/<scope>`, `ci/<scope>`.
- Commits: Conventional Commits (`feat(scope):`, `fix(scope):`, etc.). No AI co-author trailers.
- Tests: every phase requires the test categories in `CLAUDE.md` §16; the phase README spells out which ones apply.
- Reports/schemas: bumped together with code; schema/golden tests live next to the schema.
- Secrets: `.env.example` only; never commit `.env`.

---

## 7. Status, ownership, and review

- `STATUS.md` tracks the active phase, sub-phase, task, and any blockers. Update it on every commit that advances or completes a task.
- Every phase ends with a **Phase Gate Review** AND a recorded entry in the **PR & merge log** (branch, PR URL, green CI run URL, merge commit SHA, merge date). The reviewer (human or agent) checks the gates listed in that phase's README, signs the review section, drives the push/CI/merge in `PROMT.md` step 7, and only then is the next phase unlocked.
- The phase gate is hard: no advancing past a phase with deferred scope, broken tests, missing docs, unupdated PRD/CLAUDE.md, or an unmerged feature branch. If a "follow-up" item ever appears in an end-of-phase summary, that item is in-scope for the current phase — reply `Resolve the gaps you reported before proceeding.` and the agent will pick it up.

---

## 8. Final reminder

SentinelQA's whole purpose (`CLAUDE.md` §45) is to make a single question answerable with evidence: **"Can this software be trusted enough to ship?"** Every phase, sub-phase, and task in this folder exists to make our own product answer that question for itself first.
