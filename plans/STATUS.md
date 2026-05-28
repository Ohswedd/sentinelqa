# SentinelQA — Live Status

Update this file on every commit that advances or completes work. Do not advance the phase pointer past unfinished items.

## Active pointer

- **Phase:** 06 — Planner Module
- **Sub-phase:** _to be determined from `plans/phase-06-planner-module/README.md`_
- **Active task:** first task in `plans/phase-06-planner-module/` (Phase 05 merged to `main` as `2fde372`).
- **Branch:** to be created (`feature/phase-06-…`); Phase 05 branch deleted on merge.
- **Blockers:** none. Phase 05 merged 2026-05-28 (PR #6, `2fde372`). `make ci` green at merge time (531 Python + 115 TS = 646), `make coverage` 95.53 % (floor 95 %), TS coverage 93.99 % lines / 79.55 % branches (floors 85 / 75). ADR-0010 accepted. PRD §9.1 expanded with §9.1.1.
- **Last updated:** 2026-05-28 by ohswedd

---

## Phase progress

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

- [x] Phase 00 — Foundation
- [x] Phase 01 — Core Domain & Config
- [x] Phase 02 — CLI Skeleton & Run Lifecycle
- [x] Phase 03 — Report Schemas & Reporter
- [x] Phase 04 — TypeScript Playwright Runtime
- [x] Phase 05 — Discovery Module
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
| 03 | done | PASS | ohswedd | 2026-05-27 | All eight tasks (03.01–03.08) shipped on branch `feature/phase-03-report-schemas-reporter`. Wire schemas under `packages/shared-schema/`: `run.schema.json`, `findings.schema.json`, `score.schema.json` (all draft 2020-12); vendored `external/sarif-2.1.0.json` (3 389 lines, official OASIS) and `external/junit.xsd` (permissive Surefire subset). Writers: `engine/reporter/run_writer.py` (write_run + canonical_config_digest + derive_release_decision + summarize_modules_and_findings), `findings_writer.py` (write_findings with PRD §20 evidence enforcement at medium+), `findings_linter.py` (L-FND-001..004 codes), `score_writer.py` (deterministic float formatting, DEFAULT_POLICY overlay), `junit_writer.py` (Surefire mapping + system-out redaction proven by Authorization-header test), `sarif_writer.py` (severity→level mapping, SarifRuleRegistry with synthesized GEN-* fallback), `markdown_writer.py` (deterministic + md_escape over the full `\`*_{}[]()#+-.!|<>` set). Dispatcher: `engine/reporter/dispatcher.py` exposes `Reporter`, `ReportInputs`, `ReporterPlugin` Protocol, `register_reporter_hook`. Lifecycle integration: `RunLifecycle.__init__` registers the hook idempotently on `GENERATE_REPORTS`; status + finished_at finalized at the start of generate_reports; `persist_artifacts` reduced to latest-pointer write; new ctx fields `typed_findings`/`typed_module_results`/`typed_score`/`typed_policy`. `run.json` always written regardless of formats (CLAUDE §11). `json` alias expands to run + findings + score; `html` is a Phase-15 placeholder. Each emit produces one `artifact_emitted` line in audit.log. Goldens: 22 byte-locked fixtures under `tests/golden/reports/` (run.passed/unsafe/dry_run; findings.empty/critical/mixed/redacted; score.pass/blocked/warnings/unsafe/dry_run; junit/passing/failed/empty; sarif/empty/critical/mixed; markdown.passing/blocked/unsafe/dry_run). `make update-goldens` prompts for confirmation; `FORCE=1` bypasses for CI. Schema-validity check (`tests/integration/reporter/test_schemas_are_valid.py`) walks every committed `*.schema.json` (21 entries) + the vendored SARIF schema and validates each against its meta-schema. Hypothesis property tests (slow tier) generate randomized findings and prove findings.json validates, JUnit XML parses, SARIF docs validate against the official schema. `.pre-commit-config.yaml` excludes `tests/golden/` from trailing-whitespace + end-of-file fixers so goldens stay byte-stable. PRD §20 expanded to §20.1 (Persisted artifacts table), §20.2 (Finding evidence requirement), §20.3 (Schema drift guard). ADR-0008 (Report schemas & reporter pipeline) accepted; ADR README index updated to include 0005–0008. `make ci` green (434 passed); `make test-full` 443 passed (+9 slow incl. 3 property); `make coverage` 95.00% (floor met). 0 AI co-author trailers. |
| 04 | done | PASS | ohswedd | 2026-05-28 | All eight tasks (04.01–04.08) shipped on branch `feature/phase-04-typescript-playwright-runtime`. `@sentinelqa/ts-runtime` is wired with the strict tooling (composite tsconfig + tsc-build emit + postbuild shebang, `engines.node ≥ 20`, four subpath exports). Sentinel-ts CLI ships `--help`, `--version`, `run`, `list-tests`, `validate-helpers` with the deterministic exit-code grid (0/1/2/7). Custom Playwright reporter (`src/reporter.ts`) translates `onBegin/onTestBegin/onStepBegin/onStepEnd/onTestEnd/onEnd` into JSONL events; runner (`src/runner.ts`) spawns Playwright with that reporter via the workspace bin (or `npx playwright` fallback), captures stderr and forwards it only on non-zero exit. JSONL protocol: `packages/shared-schema/ts-events.schema.json` (Draft 2020-12, 14 event kinds, envelope `type+schema_version+seq+ts`), `engine/orchestrator/ts_bridge.py` (Pydantic models + `parse_event` + `stream_events` async iterator). PROTOCOL_VERSION=`1.0.0` checked by parity test against `src/protocol.ts`. Helpers (`src/helpers.ts`): `sentinelStep`, `captureEvidence` (screenshot+DOM+HAR refs), `redactedNetwork`, `redactedConsole` (warning→warn level mapping + redacted message + redacted source URL), `captureDomSnapshot` (writes HTML + emits dom.snapshot + returns sha256 AX-tree hash for the Phase-20 Healer), `harConfig` (per-test deterministic HAR path). `sentinelTest` in `src/playwright.ts` extends Playwright's `test` with `sentinel` fixture + opt-in `_network` auto-fixture; `SENTINEL_PLAYWRIGHT_DEFAULTS` matches CLAUDE §21 (trace on-first-retry, screenshot only-on-failure, video retain-on-failure). Semantic-first locator utilities (`src/locators.ts`): `bestLocator` (strategy chain `getByRole→…→getByTitle`), `describeLocator` (role/name/text/landmarks/tagName via `evaluate`), `auditLocatorBrittleness` (ts-morph AST walk; flags `:nth-of-type`, raw XPath, nested-div soup, class-prefix matchers, raw-only-no-semantic catch-all). Redaction parity: `scripts/export-redaction-rules.py` + `scripts/export-redaction-parity.py` + `scripts/export-ts-events-parity.py` write canonical fixtures; `--check` modes are CI drift gates; `.gitleaks.toml` + `detect-private-key` extended for the new fixture paths only (production code still rejected). Fixture sample-app (`packages/ts-runtime/fixtures/`) with `serve.mjs` (Node http) + `index.html` / `success.html` + a gated Chromium smoke (`SENTINELQA_HAS_CHROMIUM=1` runs `fixtures/specs/login.spec.ts`). `make ci` green: 477 Python tests + 105 TS tests = 582. `make test-full` 486 Python (+9 slow inc. 3 hypothesis). `make coverage` Python 95.71%; TS coverage gate enforced in `vitest.config.ts` (88.97 lines / 75.62 branches / floors 85 / 75). ADR-0009 (Python ↔ TS JSONL protocol) accepted; PRD §15 expanded to §15.1–§15.7 documenting sentinel-ts contract, JSONL protocol, evidence defaults, locator strategy, and safety boundary. 0 AI co-author trailers. |
| 05 | done | PASS | ohswedd | 2026-05-28 | All eight tasks (05.01–05.08) shipped on branch `feature/phase-05-discovery-module`. `engine.discovery` ships the HTTP-first MVP: `Crawler` (httpx + robots.txt + token-bucket rate limit + transparent `SentinelQA/<ver>` UA + `X-SentinelQA-Test-Run` header, pluggable `CrawlBackend` Protocol), `DomMapBuilder` (BS4 element extraction, missing-label observations, repeated-component heuristic, unreachable-link detection), `FormsInventory` (fields, validation hints, reCAPTCHA flag, no-secrets), `ApiDetector` (path templating with `[id]`/`[uuid]`/`[hex]`, 5xx detection, JS-bundle referenced-only detection), `AuthBoundaryDetector` (anon + authenticated passes, UI-only-auth + escalation hints, env-var-name-only artifacts), `OpenAPIIngester` (3.x JSON/YAML/URL ingest + meta-validation + cross-check), `GraphQLIngester` (SDL + introspection), ten-rule deterministic `risk_model` + `build_risk_map`. `sentinel discover --url ...` replaces the Phase 02 stub, runs lifecycle steps 1–8, enforces safety BEFORE any I/O, and writes `discovery.json` + `forms.json` + `api.json` + `auth.json` + `risk.json` + `discovery.report.md`. ADR-0010 (Discovery MVP is HTTP-first; SPA Playwright backend re-homed to Phase 17 task 07) accepted. PRD §9.1 expanded with §9.1.1 (MVP delivery). `make ci` green (531 Python + 115 TS = 646 tests). `make coverage` 95.53 % (floor 95 %). 0 AI co-author trailers. |
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

## PR & merge log

Every phase ends with a push → PR → CI → merge cycle handled by the loop prompt (see `PROMT.md` step 7). Record each phase's branch, PR, the CI run that turned the PR green, and the merge commit SHA on `main`. A phase row in the **Phase Gate Reviews** table above is not considered final until its row here is filled in.

| Phase | Branch | PR URL | Green CI run | Merge commit SHA | Merged on |
|---|---|---|---|---|---|
| 00 | feature/phase-00-foundation | (merged before PR & merge log existed) | — | — | 2026-05-27 |
| 01 | feature/phase-01-core-domain-config | PR #1 (Ohswedd/sentinelqa) | — | — | 2026-05-27 |
| 02 | feature/phase-02-cli-skeleton-run-lifecycle | — | — | — | 2026-05-27 |
| 03 | feature/phase-03-report-schemas-reporter | — | — | — | 2026-05-27 |
| 04 | feature/phase-04-typescript-playwright-runtime | https://github.com/Ohswedd/sentinelqa/pull/4 | https://github.com/Ohswedd/sentinelqa/actions/runs/26566004743 | bcce8b896af3c245dbbf4d92be131db2ce4f31f0 | 2026-05-28 |
| 05 | feature/phase-05-discovery-module | https://github.com/Ohswedd/sentinelqa/pull/6 | https://github.com/Ohswedd/sentinelqa/actions/runs/26574849155 | 2fde372595a40655fd282eda19a4d97f69556cd5 | 2026-05-28 |
| 06 | — | — | — | — | — |
| 07 | — | — | — | — | — |
| 08 | — | — | — | — | — |
| 09 | — | — | — | — | — |
| 10 | — | — | — | — | — |
| 11 | — | — | — | — | — |
| 12 | — | — | — | — | — |
| 13 | — | — | — | — | — |
| 14 | — | — | — | — | — |
| 15 | — | — | — | — | — |
| 16 | — | — | — | — | — |
| 17 | — | — | — | — | — |
| 18 | — | — | — | — | — |
| 19 | — | — | — | — | — |
| 20 | — | — | — | — | — |
| 21 | — | — | — | — | — |
| 22 | — | — | — | — | — |
| 23 | — | — | — | — | — |
| 24 | — | — | — | — | — |
| 25 | — | — | — | — | — |
| 26 | — | — | — | — | — |
| 27 | — | — | — | — | — |
| 28 | — | — | — | — | — |
| 29 | — | — | — | — | — |

> **Rule change effective 2026-05-28:** the loop prompt now requires push → CI-watch → merge on `main` as part of closing every phase. Phase 04 was retroactively closed under the new rule: PR #4 was merged on 2026-05-28 (squash, branch deleted) and this table backfilled on the same day. From Phase 05 onward the close-out happens inside the phase loop and no row should ever sit in `_pending_`.

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
| 2026-05-27 | 03 | PRD.md | §20 Evidence and Reporting Requirements — added §20.1 (Persisted artifacts table mapping every Phase-03 artifact to its schema + writer), §20.2 (Finding evidence requirement; critical/high/medium without evidence is rejected at write time), §20.3 (Schema drift guard: meta-schema check + byte-locked goldens + hypothesis property tests). The persisted shapes for `run.json`/`findings.json`/`score.json` are new wire formats (not domain models) and are versioned via `schema_version` at the root; ADR-0008 owns the rationale. CLI/SDK contracts not changed beyond the existing `config.report.formats` literal. | (this branch) |
| 2026-05-28 | 04 | PRD.md | §15 TypeScript Runtime Specification — expanded §15.1 (purpose + subpath exports), kept §15.2 (generated-test example now uses `@sentinelqa/ts-runtime/playwright` and the `sentinel` fixture), added §15.3 (sentinel-ts binary contract + exit codes), §15.4 (JSONL event protocol with all 14 kinds + ts-events schema + ADR-0009 link), §15.5 (evidence capture defaults aligned to CLAUDE §21 + AX-tree hash for the Healer), §15.6 (semantic locator strategy chain consumed by Phase 07 / 20), §15.7 (safety boundary + Python-authoritative redaction with byte-parity fixture). New wire format (`ts-events.schema.json` v1.0.0) is locked by ADR-0009; CLI/SDK contracts in §13 / §14 are unchanged. | (this branch) |
| 2026-05-28 | 05 | PRD.md | §9.1 Discovery module — added §9.1.1 (MVP delivery): names every shipped class in `engine.discovery`, documents the deterministic risk-rule set, lists the five JSON artifacts + Markdown summary `sentinel discover` writes, restates the safety boundary (env-var-only credentials, login body never persisted, allowlist enforced before I/O), reserves `discovery.engine: playwright` for Phase 17. ADR-0010 owns the rationale. | (this branch) |
| 2026-05-28 | 05 | CLAUDE.md | _(no edit)_ — Phase 05 adds a module package, an ADR, and a CLI command; it doesn't change a project-wide engineering rule, so CLAUDE.md is untouched. Sync log entry intentionally records the no-op. | n/a |
