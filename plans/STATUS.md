# SentinelQA — Live Status

Update this file on every commit that advances or completes work. Do not advance the phase pointer past unfinished items.

## Active pointer

- **Phase:** 03 — Report Schemas & Reporter
- **Sub-phase:** 03.06 — Markdown report
- **Active task:** `phase-03-report-schemas-reporter/06-markdown-report.md`
- **Branch:** `feature/phase-03-report-schemas-reporter`
- **Blockers:** none. Task 03.01 closed: `run.schema.json` (draft 2020-12) committed under `packages/shared-schema/`; `engine/reporter/run_writer.py` ships `write_run` + helpers (`canonical_config_digest`, `derive_release_decision`, `summarize_modules_and_findings`); three goldens (`run.passed/unsafe/dry_run.golden.json`) lock the wire format; shared fixtures live in `tests/conftest.py`; `make update-goldens` regenerates goldens deliberately. `make ci` green (330 passed); `make coverage` 95.69%.
- **Last updated:** 2026-05-27 by ohswedd

---

## Phase progress

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

- [x] Phase 00 — Foundation
- [x] Phase 01 — Core Domain & Config
- [x] Phase 02 — CLI Skeleton & Run Lifecycle
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
| 00 | done | PASS (CI-on-remote verification closed during Phase 01 — see Notes) | ohswedd | 2026-05-27 | All nine tasks (00.01–00.09) shipped on branch `feature/phase-00-foundation`. `make ci` green: ruff format-check + ruff lint + mypy strict + adr-check + pytest (4 tests) + Prettier + ESLint (3 workspaces) + tsc + Vitest (2 tests). pre-commit (gitleaks + commitlint + pre-push make-ci) wired and probed. ADRs 0001–0004 accepted. Repo tree matches PRD §11.2 exactly (41 directories). 0 AI co-author trailers in 11 commits. gitleaks: 0 leaks across 739 KB of history. **Verification gap closed (2026-05-27):** the private GitHub repo `Ohswedd/sentinelqa` was created at the end of Phase 01; PR #1 (Phase 01 → main) exercised all 8 required checks. The first run surfaced two genuine Phase-00 workflow bugs — `gitleaks-action@v2` crashed when trying to upload a SARIF artifact that was never written (no leaks), and `lychee --base .` failed because lychee 0.23 requires an absolute path or URL. Both fixed in commit `3148fd4`; all 8 checks green afterward. Branch protection on `main` could not be wired via API because GitHub gates that feature behind GitHub Pro for private repos; the user-facing equivalent (pre-push hook + CODEOWNERS + Conventional Commits in CI) is in place locally and on the remote checks. |
| 01 | done | PASS | ohswedd | 2026-05-27 | All eight tasks (01.01–01.08) shipped on branch `feature/phase-01-core-domain-config`. `make ci` green: ruff format-check + ruff lint + mypy strict + adr-check + pytest (193 tests with `make test-full`, 187 with default markers) + Prettier + ESLint + tsc + Vitest. `make coverage` reports 96.24% (floor: 95%). Domain models: every PRD §18.1 entity is a frozen Pydantic v2 model with prefix-based ID generator, `extra="forbid"`, and SCHEMA_VERSION ClassVar; `make schemas` writes 17 stable `*.schema.json` files into `packages/shared-schema/schemas/`. Config: strict `sentinel.config.yaml` loader with `${ENV}` interpolation, unknown-key rejection, inline-secret refusal; `sentinel.config.yaml.example` round-trips. Safety: `SafetyPolicy.enforce` covers local/allowlisted/destructive branches; `UnsafeTargetError` → exit 4; audit log writes redacted JSONL; forbidden-feature deny-list scanned by `tests/security/test_no_stealth_flags.py`. Errors: typed hierarchy (`SentinelError` → 11 subclasses), `to_agent_message()` redacted; exit codes 0/1/2/3/4/5/6/7 wired through `engine.errors.codes.ERROR_REGISTRY`. Redaction: real impl, header + URL + dict surfaces, entropy heuristic + hypothesis property tests (10 000 examples slow tier). Logging: human/JSON/quiet modes, redaction filter on every record, context-var enrichment. ADR-0005 (Config schema), ADR-0006 (Safety policy), `docs/dev/schema-versioning.md`, and `docs/user/error-codes.md` shipped. PRD §13.2 was corrected to the canonical 8-code exit grid in the same branch (sync log entry below). 0 AI co-author trailers. |
| 02 | done | PASS | ohswedd | 2026-05-27 | All eight tasks (02.01–02.08) shipped on branch `feature/phase-02-cli-skeleton-run-lifecycle`. `sentinel --help` lists every PRD §13.1 command (init/doctor/audit implemented; the other 16 are registered stubs that exit 7 with a "lands in Phase NN" message — CLAUDE §37, no fake completion). `sentinel --version` returns the pyproject version. `sentinel init` is idempotent, `--force`-safe, and the bundled `.github/workflows/sentinel.yml` is byte-equal to PRD §21.1. `sentinel doctor` runs Python/Node/Playwright/config/safety/reachability/env-var/`.sentinel`-writable/disk checks with human ASCII or single-line JSON output. The canonical 17-step run lifecycle lives at `engine/orchestrator/run_lifecycle.py`: safety policy is enforced exactly once (unsafe → exit 4 with audit.log + minimal run.json), `--dry-run` stops after `build_execution_plan` with `status="dry_run"`, module errors mark the run `incomplete` (exit 6) without crashing the run, `--ci` forces JSON mode + no prompts. Artifact tree per CLAUDE §11 with atomic writes (write → fsync → rename), retention helper (`prune_old_runs`, pinned-run support), POSIX symlink/Windows marker for `latest`. JSON-mode purity proven by a `SENTINELQA_ASSERT_JSON_STDOUT=1` write-guard that fails fast on non-JSON stdout. CLI exit-code grid (0–7) fully reachable in tests via `CliRunner`. Engine reorganized as a workspace member (`engine/pyproject.toml`) so `pip install -e apps/cli` brings in `sentinelqa-engine` automatically; typer pinned at 0.15.1 + click 8.1.8 (click 8.2+ broke the `Parameter.make_metavar` API). `make ci` green: ruff format-check + ruff lint + mypy strict (133 source files) + adr-check (7 ADRs incl. new ADR-0007) + pytest (306 default markers; `make test-full` 312 with slow tier). `make coverage` 95.47% (floor 95%); CLI-only coverage 92.32% (over the 90% Phase-02 floor). `make schemas` regenerates 17 schemas; `test_run.schema.json` enum gains `dry_run`. `git status` clean. 0 AI co-author trailers. |
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
| 2026-05-27 | 02 | _(none)_ | Phase 02 implements behavior PRD §10–§13, §17, and §26 already specify in full. The CLI now exists at `apps/cli/src/sentinel_cli/`, but every command listed in PRD §13.1 was already promised — three are implemented (`init`, `doctor`, `audit`), the other 16 remain phase-stubbed per PRD §32 (recommended build order) and CLAUDE.md §37 (no fake completion). The 17-step run lifecycle codified in `engine/orchestrator/run_lifecycle.py` matches CLAUDE.md §10 step-for-step. The new `RunStatus="dry_run"` value is an additive enum expansion in `engine.domain.test_run` and `packages/shared-schema/schemas/test_run.schema.json`; PRD §18.1 lists entities by name only (no enum surface), so no PRD §18 text changed. JSON-mode purity (CLAUDE §13) is now enforced and tested. Exit-code grid behavior is unchanged from the Phase-01 row above — Phase 02 only wires the runtime mapping (`failed`→1, `unsafe_blocked`→4, `incomplete`→6, `dry_run`→0). | (this branch) |
