# SentinelQA — Live Status

Update this file on every commit that advances or completes work. Do not advance the phase pointer past unfinished items.

## Active pointer

- **Phase:** 02 — CLI Skeleton & Run Lifecycle
- **Sub-phase:** 02.01 — Typer CLI scaffold
- **Active task:** `phase-02-cli-skeleton-run-lifecycle/01-cli-skeleton.md` (to be opened when Phase 02 starts)
- **Branch:** _(to be created off `main` once Phase 01 is merged; local `main` will be fast-forwarded to the Phase-01 branch tip as a stand-in until a remote exists.)_
- **Blockers:** none. The Phase 00 CI verification gap still stands (no GitHub remote); first push to a remote MUST exercise the 5 workflows.
- **Last updated:** 2026-05-27 by ohswedd

---

## Phase progress

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

- [x] Phase 00 — Foundation
- [x] Phase 01 — Core Domain & Config
- [ ] Phase 02 — CLI Skeleton & Run Lifecycle
- [ ] Phase 03 — Report Schemas & Reporter
- [ ] Phase 04 — TypeScript Playwright Runtime
- [ ] Phase 05 — Discovery Module
- [ ] Phase 06 — Planner Module
- [ ] Phase 07 — Generator Module
- [ ] Phase 08 — Runner Module
- [ ] Phase 09 — Analyzer Module
- [ ] Phase 10 — Functional Module
- [ ] Phase 11 — Accessibility Module
- [ ] Phase 12 — Performance Module
- [ ] Phase 13 — Security (Safe) Module
- [ ] Phase 14 — Quality Scoring
- [ ] Phase 15 — HTML & JSON Reports
- [ ] Phase 16 — Python SDK
- [ ] Phase 17 — CI Integration
- [ ] Phase 18 — MCP & Agent Interface
- [ ] Phase 19 — LLM-Code Audit Module
- [ ] Phase 20 — Healer / Self-Repair
- [ ] Phase 21 — Visual Regression
- [ ] Phase 22 — API Testing
- [ ] Phase 23 — Chaos Module
- [ ] Phase 24 — Plugin Architecture
- [ ] Phase 25 — Integrations
- [ ] Phase 26 — Example Apps
- [ ] Phase 27 — Docs & ADRs
- [ ] Phase 28 — Versioning & Release Prep
- [ ] Phase 29 — Final Hardening & PRD Reconciliation

---

## Phase Gate Reviews

For each phase, record the gate review verdict and the reviewer's signature once the phase is complete. A phase is **not** considered done until its gate row is filled in here.

| Phase | Status | Gate verdict | Reviewer | Date | Notes / linked commit |
|---|---|---|---|---|---|
| 00 | done | PASS (with CI-on-remote verification deferred to first PR — see Notes) | ohswedd | 2026-05-27 | All nine tasks (00.01–00.09) shipped on branch `feature/phase-00-foundation`. `make ci` green: ruff format-check + ruff lint + mypy strict + adr-check + pytest (4 tests) + Prettier + ESLint (3 workspaces) + tsc + Vitest (2 tests). pre-commit (gitleaks + commitlint + pre-push make-ci) wired and probed. ADRs 0001–0004 accepted. Repo tree matches PRD §11.2 exactly (41 directories). 0 AI co-author trailers in 11 commits. gitleaks: 0 leaks across 739 KB of history. **Verification gap:** the 5 GitHub Actions workflows (ci, secret-scan, commitlint, no-ai-coauthor, link-check) have NOT executed on a real PR because the repo has no GitHub remote yet. Documented in `docs/dev/ci-and-branch-protection.md`. The first push to a GitHub remote MUST exercise all 5 workflows; any divergence between docs and runtime is a Phase-00 bug to fix before Phase 01 begins. |
| 01 | done | PASS | ohswedd | 2026-05-27 | All eight tasks (01.01–01.08) shipped on branch `feature/phase-01-core-domain-config`. `make ci` green: ruff format-check + ruff lint + mypy strict + adr-check + pytest (193 tests with `make test-full`, 187 with default markers) + Prettier + ESLint + tsc + Vitest. `make coverage` reports 96.24% (floor: 95%). Domain models: every PRD §18.1 entity is a frozen Pydantic v2 model with prefix-based ID generator, `extra="forbid"`, and SCHEMA_VERSION ClassVar; `make schemas` writes 17 stable `*.schema.json` files into `packages/shared-schema/schemas/`. Config: strict `sentinel.config.yaml` loader with `${ENV}` interpolation, unknown-key rejection, inline-secret refusal; `sentinel.config.yaml.example` round-trips. Safety: `SafetyPolicy.enforce` covers local/allowlisted/destructive branches; `UnsafeTargetError` → exit 4; audit log writes redacted JSONL; forbidden-feature deny-list scanned by `tests/security/test_no_stealth_flags.py`. Errors: typed hierarchy (`SentinelError` → 11 subclasses), `to_agent_message()` redacted; exit codes 0/1/2/3/4/5/6/7 wired through `engine.errors.codes.ERROR_REGISTRY`. Redaction: real impl, header + URL + dict surfaces, entropy heuristic + hypothesis property tests (10 000 examples slow tier). Logging: human/JSON/quiet modes, redaction filter on every record, context-var enrichment. ADR-0005 (Config schema), ADR-0006 (Safety policy), `docs/dev/schema-versioning.md`, and `docs/user/error-codes.md` shipped. PRD §13.2 was corrected to the canonical 8-code exit grid in the same branch (sync log entry below). 0 AI co-author trailers. |
| 02 | not started | — | — | — | — |
| 03 | not started | — | — | — | — |
| 04 | not started | — | — | — | — |
| 05 | not started | — | — | — | — |
| 06 | not started | — | — | — | — |
| 07 | not started | — | — | — | — |
| 08 | not started | — | — | — | — |
| 09 | not started | — | — | — | — |
| 10 | not started | — | — | — | — |
| 11 | not started | — | — | — | — |
| 12 | not started | — | — | — | — |
| 13 | not started | — | — | — | — |
| 14 | not started | — | — | — | — |
| 15 | not started | — | — | — | — |
| 16 | not started | — | — | — | — |
| 17 | not started | — | — | — | — |
| 18 | not started | — | — | — | — |
| 19 | not started | — | — | — | — |
| 20 | not started | — | — | — | — |
| 21 | not started | — | — | — | — |
| 22 | not started | — | — | — | — |
| 23 | not started | — | — | — | — |
| 24 | not started | — | — | — | — |
| 25 | not started | — | — | — | — |
| 26 | not started | — | — | — | — |
| 27 | not started | — | — | — | — |
| 28 | not started | — | — | — | — |
| 29 | not started | — | — | — | — |

---

## Deferred-scope register

This table must remain empty at every phase boundary. If a phase needs to defer something, it must be planned into a future phase and added to that phase's task list **before** the gate review passes. Items here at gate time block the phase from closing.

| Date | Phase | Item | Why deferred | Re-homed to phase | Resolved? |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

---

## PRD / CLAUDE.md sync log

Whenever a phase changes behavior, schemas, or boundaries, record the doc update here.

| Date | Phase | Doc updated | Section(s) | Commit |
|---|---|---|---|---|
| 2026-05-27 | 00 | _(none)_ | Phase 00 introduced no behavior changes, no schema changes, no safety-boundary changes, no scoring changes, and no CLI/SDK contract changes. PRD.md and CLAUDE.md were both untouched (PRD trailing whitespace was inadvertently rewritten by the pre-commit hook during a probe and immediately restored; PRD.md, CLAUDE.md were added to the trailing-whitespace + end-of-file-fixer exclude list to make the protection permanent). No sync entry required. | n/a |
| 2026-05-27 | 01 | PRD.md | §13.2 Exit codes — replaced 7-code informal grid with the canonical 8-code grid from CLAUDE.md §13; now lists the Phase 01 exception type bound to each code so `engine/errors/codes.py` is the single source of truth. Conflict resolution per CLAUDE §2 authority order (CLAUDE > PRD). | a5ab2d1 |
| 2026-05-27 | 01 | _(none beyond §13.2)_ | Phase 01 introduces typed core models, the strict config loader, the safety policy, the redaction layer, and the structured logger. None of those changes alter externally-observable product behavior beyond the exit-code grid logged above. CLI/SDK contracts have not shipped yet (Phase 02+), so the PRD's §13.1 CLI and §14 SDK sections did not need updating. | (this branch) |
