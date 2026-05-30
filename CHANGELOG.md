# Changelog

All notable changes to SentinelQA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
under the pre-1.0 rules in [`docs/dev/semver.md`](docs/dev/semver.md). Until the
first `1.0.0` tag is published, breaking changes are allowed in minor versions
but MUST be documented under the `Changed` or `Removed` heading of the version
that introduces them.

Drafts are generated from Conventional Commits with
`make changelog-draft` (which runs `scripts/release/draft_changelog.py`). The
human owner curates the draft before each tag.

## [Unreleased]

### Added

- **plans/phase-30-llm-providers/** — Multi-provider LLM adapter layer. Generalises the planner/analyzer/healer LLM Protocols into a single `engine.llm.LlmProvider` surface; adds adapters for Google Gemini, Ollama (local), Azure OpenAI, Google Vertex AI, Mistral, Groq, OpenRouter. Shared cost / budget / rate-limit / redaction plumbing; `sentinel llm doctor` / `list` / `price` CLI surface.
- **plans/phase-31-browser-auth/** — Browser-authenticated audits. Encrypted storage-state vault, `sentinel auth login` interactive flow, OAuth + LLM-web profile recipes (Google / GitHub / Microsoft + Claude / ChatGPT / Codex / Gemini / Le Chat), vault-aware runner + crawler wiring, layered safety guards.
- **plans/phase-32-extended-security/** — Extended security skill catalog (9 new checks, no offensive material). JWT weakness scanner, extended cookie audit, TLS / cert posture probe, GraphQL safety probe, OWASP-API-Top-10 BOLA/BFLA via authorized identity replay, deeper frontend-only auth detector, secret-in-bundle scanner, SSRF / open-redirect map, CWE / MITRE ATT&CK / OWASP-API id mapping on every security + API finding.
- **plans/phase-33-supply-chain/** — Supply-chain & dependency audit. CycloneDX 1.5 SBOM generator, OSV vulnerability lookup, lockfile freshness gate, postinstall-hook scanner, Trivy / Grype container scanner adapter, SPDX license audit, `sentinel supply-chain` CLI.
- **plans/phase-34-compliance/** — Compliance packs. WCAG 2.2 axe upgrade + 5 deterministic checks, GDPR cookie-consent detection, CCPA Do-Not-Sell link check, SOC 2 audit-trail quality gate, compliance-pack policy DSL with four built-in packs.
- **plans/phase-35-public-release/** — Public release engineering. README polish with badges and quickstart, GitHub community files (issue templates, CoC, SECURITY.md, CONTRIBUTING polish), license-header audit, Cloudflare Pages docs deploy, brand assets, branch-protection documentation, Dependabot + GitHub Security Advisories, owner-gated "go public" checklist.
- **plans/phase-36-publish-ecosystem/** — Ecosystem publish. v1.0.0 tag prep (manifests bump + curated CHANGELOG), PyPI Trusted-Publisher workflow, npm publish workflow with provenance, Docker Hub multi-arch publish (amd64 + arm64), GitHub Release with binaries, post-publish smoke test, owner-only publish runbook.
- **docs/PRD.md §7.3** updated — original future-scope split into "moved in-scope (Phases 30–36)" and "still future-scope". Out-of-scope items remain ADR-anchored.
- **plans/README.md** — phase table extended to 37 phases; PRD → phase mapping updated.
- **plans/STATUS.md** — Phase 30–36 added as `[ ]`, PR & merge log carries Phase 29 release-prep row, active pointer flipped from "build complete" to "Phase 30 planned (not yet started)".

### Changed

- **Project framing**: the README headline status moves from `Stable (pre-1.0)` to a forward-looking pointer at Phases 30–36 (MVP complete; ecosystem expansion in progress). v1.0.0 lands at the end of Phase 36.

### Status

This is **planning only** — no production code changed in this commit. Each of the seven new phases will land via its own `feature/phase-NN-<slug>` branch + PR + CI + squash-merge, same as Phases 00–29.

## [0.7.0] - 2026-05-31

## [0.7.0] - 2026-05-31

Captures Phases 28 and 29. **First publication-eligible tag** — owner approval
required per `CLAUDE.md` §40 and the trademark rows in
`docs/release/pre-1.0-review.md`.

### Added

- **phase-28**: Release-engineering surface. Pre-1.0 semver policy at
  `docs/dev/semver.md`, this `CHANGELOG.md`, the
  `scripts/release/draft_changelog.py` drafter (and `cliff.toml` + the
  `.github/changelog-template.md` GitHub release-notes template). Every
  publishable Python `pyproject.toml` gains release-ready
  `keywords` / `classifiers` / `project.urls`;
  `packages/ts-runtime/package.json` gains `license` / `repository` /
  `author` / `keywords` / `files` / `homepage` / `bugs` / `engines`
  (`private:true` preserved). Audit gate
  `scripts/release/audit_metadata.py` (`make audit-metadata`) rejects
  AI authors. Build pipeline `scripts/release/build_all.py`
  (`make build-all`) produces 6 Python sdists + 6 wheels + 1 TS tarball.
  Inspection gate `scripts/release/inspect_built_packages.py`
  (`make inspect-all`) rejects `.git/`, `.env`, PEM/SSH keys, cloud
  credentials, `__pycache__/`, `*.pyc`. `docs/dev/trademarks-and-naming.md`
  (Stable verdict; common-law lanes cleared). `docs/release/pre-1.0-review.md`
  (the human-owner sign-off gate covering every CLAUDE.md §40 bullet).
  `modules/` and `integrations/` are now their own workspace members
  (`sentinelqa-modules`, `sentinelqa-integrations`).
- **phase-29**: Final hardening & PRD reconciliation. Nine audit
  deliverables under `docs/release/` — safety, secret-leak, determinism,
  perf + bench JSON, output-a11y, PRD coverage, CLAUDE.md coverage, and
  DoD-sweep audits, all dated `2026-05-30`. Live red-team probe against
  `https://example.com` refused with exit 4 + `E-SAFE-001`. gitleaks +
  13-rule pattern sweep over `.sentinel/runs/` returned zero hits across
  2 442 files. Reporter writers byte-equal across N=3 runs modulo the
  documented volatile fields. `sentinel doctor` 778 ms / 3 000 ms budget.
  Eleven static WCAG-2.1 anchors green on the Phase 15 HTML report.
- **phase-29**: New helpers. `scripts/diff_runs.py` normalises volatile
  fields when comparing run trees; `scripts/bench.py` drives the
  wall-clock budgets. New Make targets `bench` and `dod` (Definition-of-
  Done sweep wrapping `ci` + secret-leak + determinism + git-status).
- **phase-29**: Three new recurring-audit integration tests under
  `tests/integration/release/` — `test_secret_leak.py` (no unredacted
  secrets in `.sentinel/runs/` on every CI run), `test_determinism.py`
  (per-artifact byte equality + drift detection),
  `test_report_self_a11y.py` (WCAG-2.1 anchors; Chromium lane gated
  behind `SENTINELQA_SELF_A11Y_PLAYWRIGHT=1`).
- **release**: Versions bumped to `0.7.0` across all six publishable
  Python pyprojects (`sentinelqa-cli`, `sentinelqa-engine`,
  `sentinelqa-modules`, `sentinelqa-integrations`, `sentinelqa`,
  `sentinelqa-mcp`) and `packages/ts-runtime/package.json`. The SDK and
  MCP packages moved from `0.1.0` to `0.7.0` to align with the
  monorepo's headline version (the SDK public surface is unchanged).

### Changed

- `tests/conftest.py` pins `COVERAGE_RCFILE` and `COVERAGE_FILE` env
  vars to absolute repo paths so child Python processes started during
  pytest no longer initialise statement-mode coverage and break
  `coverage combine`. Fix for a latent local-only flake; CI was
  unaffected because the workflow runs `pytest` without `--cov`.
- `.pre-commit-config.yaml` excludes
  `tests/integration/release/test_secret_leak.py` and
  `docs/release/secret-leak-audit-2026-05-30.md` from `detect-private-key`
  — both files reference the PEM regex literal as a pattern, not a key.
  gitleaks still scans them.
- `engine/pyproject.toml` migrated from `packages = ["../engine"]` to
  the `include + sources = {"" = "engine"}` mapping so `uv build`
  succeeds.

### Removed

_Nothing removed in `0.7.0`._

### Security

- Re-audited every `SafetyPolicy.enforce` call site (19 total). Live
  red-team probe against `https://example.com` refused with exit 4 +
  `E-SAFE-001`. Full verdict + per-module table in
  `docs/release/safety-audit-2026-05-30.md`.
- Secret-leak gate added as a recurring CI check
  (`tests/integration/release/test_secret_leak.py`).

## [0.6.0] - 2026-05-30

Captures Phases 26 and 27.

### Added

- **phase-26**: Example apps — Next.js, FastAPI, Django, Flask, React+Vite, an
  intentionally-broken LLM-built Next.js demo, and a `docker compose`
  end-to-end stack. Loopback-only ports; public, documented credentials.
  `Makefile` gains `demo`, `demo-down`, and per-example `demo-<name>` targets.
- **phase-27**: Astro Starlight docs site at `apps/docs/`. 33 hand-authored
  pages + 5 auto-generated pages (CLI / SDK / MCP / errors / ADR index).
  Status-label CI guard at `tests/integration/docs/test_status_labels.py`,
  ADR-completeness guard at `tests/integration/docs/test_adr_completeness.py`,
  freshness gate at `tests/integration/docs/test_generated_docs_fresh.py`.
- **phase-27**: Ten new ADRs (`docs/adr/0032`–`docs/adr/0041`): docs site
  choice, cloud boundary, and one ADR per PRD §31 open question. PRD §31.1
  cross-references each accepted ADR.
- **phase-27**: New CI job `docs (Astro Starlight)` builds the site on every
  PR; new Make targets `docs-gen-all` / `docs-gen-error-codes` / `docs-gen-cli`
  / `docs-gen-sdk` / `docs-gen-mcp` / `docs-gen-adr-index` / `docs-check-fresh`
  / `docs-build` / `docs-dev` / `docs`.

### Changed

- `pnpm-overrides` pins `zod-to-json-schema@3.24.6` and `@astrojs/sitemap@3.2.1`
  for Astro 4.16 compatibility (documented in ADR-0032).

## [0.5.0] - 2026-05-30

Captures Phases 24 and 25.

### Added

- **phase-24**: Plugin architecture. SDK-public Protocols in `sentinelqa.plugins`
  (`PROTOCOL_VERSION = "1.0.0"`, `ENTRY_POINT_GROUP = "sentinelqa.plugins"`,
  eight `@runtime_checkable` Protocols). Engine loader at `engine.plugins` with
  entry-point discovery, capability allow-list, permission grammar, subprocess
  sandbox. Plugin manifest wire format at
  `packages/shared-schema/plugin-manifest.schema.json` (Draft 2020-12, v1).
  `sentinel plugins {list, info, validate}` Typer subapp. Two reference plugins
  under `examples/plugins/`. ADR-0029.
- **phase-25**: Integrations adapter set. BrowserStack + Sauce Labs runners
  (`RunnerPlugin`-shaped), Slack poster with dedup + webhook redaction, GitHub
  status / issue, GitLab status, Jira + Linear issue creation. All adapters run
  on stdlib `urllib` via `integrations/_http.py`; all secrets read at call time,
  never logged. `sentinel report --notify slack` flag. Credential-leak guard at
  `tests/integration/integrations/test_credential_leak_guard.py`. ADR-0030.

### Changed

- `packages/python-sdk/api-snapshot.json` regenerated to pin the new
  `sentinelqa.plugins` module.
- New config blocks: `policy.github.auto_create_issue`,
  `policy.integrations.{slack, jira, linear}`. Documented in
  `sentinel.config.yaml.example`; all integrations OFF by default.

## [0.4.0] - 2026-05-29

Captures Phases 22 and 23.

### Added

- **phase-22**: API testing module (`modules/api`). Seven check kinds —
  `contract` (OpenAPI 3.x + GraphQL SDL/introspection), `negative`, `auth`,
  `latency` (skip-only; defers to Phase 12 perf), `pagination`, `error_shape`,
  `backward_compat`. Layered no-fuzz guard (config clamps + 64 KB I/O cap +
  fixed variant catalogue + AST/CLI security guard). `sentinel api` CLI
  replaces the Phase-02 stub. ADR-0027.
- **phase-23**: Chaos / adversarial module (`modules/chaos`). 13-entry scenario
  catalog (network / session / ux / data). TS chaos helpers at
  `@sentinelqa/ts-runtime/chaos`. Nine `chaos-*` rule IDs. Bounded knobs;
  default-OFF in `ModulesConfig`. `sentinel chaos` CLI replaces the last
  Phase-02 stub. ADR-0028.

### Security

- **phase-22**: `tests/security/test_api_no_aggressive_flags.py` — AST guard
  rejects `--aggressive`, `--fuzz`, `--brute`, `--stress`, `--unbounded`,
  `--no-rate-limit` in the API CLI and module source.
- **phase-23**: `tests/security/test_chaos_no_evasion_flags.py` — AST + grep
  guard rejects `stealth_mode`, `bot_detection_bypass`, `proxy_rotation`,
  `captcha_bypass`, `--undetectable`, `--bypass`, `--evade*` in the chaos
  CLI and module source.

## [0.3.0] - 2026-05-29

Captures Phases 20 and 21.

### Added

- **phase-20**: Healer / Self-Repair (`engine.healer`). Three deterministic
  proposers (locator / wait / fixture). Structural assertion-weakening guard
  (`assert_no_assertion_weakening`). Banner-aware hand-edit detection. Three-
  level auto-apply gating (`off` / `safe` / `aggressive`). New `RepairProposal`
  wire format at `packages/shared-schema/repair-proposal.schema.json` (v1).
  Analyzer ↔ Healer routing helper `is_healer_candidate`. `sentinel fix` CLI
  replaces the Phase-02 stub. MCP `sentinel.suggest_fix` surfaces persisted
  proposals; `sentinel.verify_fix` four-decision loop. ADR-0025.
- **phase-21**: Visual regression module (`modules/visual`). Pure-Python Pillow
  diff math (pixel diff + single-scale Wang et al. SSIM perceptual filter).
  Storage layout `.sentinel/baselines/<viewport>/<route-slug>.png`. Three
  default viewports (mobile / tablet / desktop). Mask grammar (`selector` or
  `rect`, wildcard `*`, prefix glob `admin*`). `sentinel visual` Typer subapp
  with `diff`, `accept`, and `capture` subcommands. Hard CI-acceptance guard
  (`sentinel visual accept` refuses in CI; exit 4; `visual.accept.refused_ci`
  audit-log entry). ADR-0026.

## [0.2.0] - 2026-05-29

Captures Phases 18 and 19.

### Added

- **phase-18**: MCP & Agent Interface. `packages/mcp-server` ships the
  pure-Python MCP server speaking JSON-RPC 2.0 over NDJSON-framed stdio at
  protocol `2024-11-05`. All twelve PRD §16.1 tools plus `sentinel.ping`.
  `AgentEnvelope` wire shape at
  `packages/shared-schema/agent-envelope.schema.json` (v1). Safety contract
  enforced by `sentinelqa_mcp.tools._safety.enforce_url` and AST guard at
  `tests/security/test_mcp_safety.py`. `sentinel mcp` CLI replaces the Phase-02
  stub. ADR-0023.
- **phase-19**: LLM-code audit module (`modules/llm_audit`). Sixteen stable
  `LLM-*` rule IDs covering dead buttons, fake routes/endpoints, mock data
  shipped, frontend-only auth, hardcoded creds, console errors, etc.
  Hardcoded-credential snippets double-redacted (`[REDACTED:hardcoded_credential]`
  before passing through `engine.policy.redaction.redact`). Reporter
  differentiator: dedicated "LLM-Code Audit" section in `report.html` and the
  PR-comment Markdown table. `sentinel llm-audit` CLI replaces the Phase-02
  stub. ADR-0024.

## [0.1.0] - 2026-05-29

Initial MVP. Captures Phases 00 through 17.

### Added

- **phase-00**: Repository scaffold per PRD §11.2. Python tooling baseline
  (uv + ruff + mypy + pytest), TypeScript tooling baseline (pnpm + tsc +
  eslint + vitest), gitleaks pre-commit, Conventional Commits CI guard,
  GitHub Actions for Python / TS / gitleaks / commitlint, Apache-2.0 license,
  CODEOWNERS, no-AI-coauthor CI guard. ADRs 0001–0004.
- **phase-01**: Core domain (`engine.domain`), strict config loader
  (`engine.config`), safety policy (`engine.policy`), redaction layer,
  typed error hierarchy with exit-code grid 0/1/2/3/4/5/6/7, structured
  logging with human/JSON/quiet modes. PRD §13.2 exit-code grid canonicalised.
  ADRs 0005–0006.
- **phase-02**: Typer CLI skeleton with every PRD §13.1 command stubbed.
  Canonical 17-step run lifecycle at `engine/orchestrator/run_lifecycle.py`.
  Per-run artifact tree `.sentinel/runs/<id>/`. JSON-mode purity enforced by
  `SENTINELQA_ASSERT_JSON_STDOUT=1` guard. `sentinel init`, `sentinel doctor`,
  `sentinel audit` implemented. ADR-0007.
- **phase-03**: Report schemas + reporter pipeline. `run.json`, `findings.json`,
  `score.json` (Draft 2020-12); vendored SARIF 2.1.0 + JUnit XSD. Reporter
  package with run / findings / score / JUnit / SARIF / Markdown writers.
  Lifecycle integration; 22 byte-locked goldens; hypothesis property tests on
  the slow tier. PRD §20.1–§20.3 added. ADR-0008.
- **phase-04**: `@sentinelqa/ts-runtime` workspace member with strict tooling
  (composite tsconfig + tsc-build + postbuild shebang). `sentinel-ts run`,
  `list-tests`, `validate-helpers`. Custom Playwright reporter emitting JSONL
  via stdout. Python ↔ TS JSONL protocol at
  `packages/shared-schema/ts-events.schema.json` (Draft 2020-12, 14 event
  kinds). Helpers: `sentinelStep`, `captureEvidence`, `redactedNetwork`,
  `redactedConsole`, `captureDomSnapshot`, `harConfig`. Semantic-first locator
  utilities + brittleness audit. ADR-0009.
- **phase-05**: HTTP-first discovery MVP (`engine.discovery`). Crawler (httpx +
  robots.txt + token bucket + transparent UA). DOM map, forms inventory, API
  detector with path templating, auth boundary detector, OpenAPI + GraphQL
  ingest. Ten-rule deterministic `risk_model` + `build_risk_map`. `sentinel
discover` CLI replaces the Phase-02 stub. ADR-0010.
- **phase-06**: Deterministic planner + optional LLM adapter (`engine.planner`).
  Eleven named extractors (login / signup / logout / pwreset / CRUD / SFS /
  admin / role / file / payment / notification). Plan wire format
  `plan.schema.json` v1. HTTP-only vendor adapters (`openai_planner.py`,
  `anthropic_planner.py`). Per-run USD budget. `sentinel plan` CLI. ADR-0011.
- **phase-07**: Deterministic Playwright spec generator (`engine.generator`).
  Jinja2 templates with `StrictUndefined`; 14 templates. Page objects with
  semantic locators only. Auth / data / global-setup-teardown fixtures
  (env-var creds only; destructive data gated on
  `security.mode=authorized_destructive`). `sentinel-ts audit-locators`
  subcommand. Banner-aware writer refuses hand-edited files. `sentinel
generate` CLI. ADR-0012.
- **phase-08**: Playwright runner (`engine.runner`). `LocalRunner` + `DockerRunner`
  sharing the `RunnerInvocation → RunnerOutcome` contract. JSONL aggregator
  with partial-stream tolerance, P50/P95 metrics, flake-rate. Strict
  quarantine list. Deterministic sharding (SHA-1 of POSIX path). Pinned
  `mcr.microsoft.com/playwright:v1.49.0-jammy` Docker image. `sentinel test`
  CLI. New wire envelope `module-results/<module>.json` v1. ADR-0013.
- **phase-09**: Deterministic analyzer (`engine.analyzer`). `categorize` over
  the closed PRD §9.5 ten-category set. `root_cause.hypothesize` with redaction-
  safe snippets. `repro.reproduction` with credential-free repro steps; spec
  emission gated by `// SENTINELQA AUTO-GENERATED REPRO SPEC` banner.
  `retry_decision.should_retry` with two-retry cap. Optional LLM refinement
  (vendor-neutral HTTP-only adapters). ADR-0014.
- **phase-10**: Functional module (`modules/functional`). Abstract
  `SentinelModule` base class (CLAUDE §9). `FunctionalModule` discovers
  `tests/sentinel/*.spec.ts`, drives the runner, translates failed tests into
  typed findings. Canonical `@p0..p3 / @module:<n> / @flow:<extractor> /
@risk:<level>` tag set. Slice modes (`smoke / standard / full`). `sentinel
functional` CLI. ADR-0015.
- **phase-11**: Accessibility module (`modules/accessibility`). Per-route
  audits via `sentinel-ts audit-a11y` subcommand. axe-core + keyboard +
  landmark + accessible-name checks. CLAUDE §28 wording guard ("Automated
  accessibility check found…"). `sentinel a11y` CLI. ADR-0016.
- **phase-12**: Performance module (`modules/performance`). Page budgets,
  API latency P50/P95, bundle/CPU long tasks, navigation stability. CLAUDE
  §27 synthetic-labelling guard. `sentinel-ts audit-perf` subcommand.
  `sentinel perf` CLI. ADR-0017.
- **phase-13**: Security (safe) module (`modules/security`). Eleven per-check
  files (headers / cookies / cors / csrf / xss reflected / xss stored gated /
  sqli gated / idor gated / frontend secrets / deps / sast). 23 stable
  `SEC-*` rule IDs registered with the SARIF writer. Stored XSS / SQLi
  require `security.mode=authorized_destructive` + valid proof-of-authorization.
  AST guard at `tests/security/test_module_calls_policy.py`. `sentinel
security` CLI. ADR-0018.
- **phase-14**: Quality scoring (`engine.scoring`). Eight PRD §19.1 axes;
  `compute_blockers` (CLAUDE §25); typed `PolicyDecision`. `sentinel report
--explain-score` CLI. Hypothesis 5000-example property test + three byte-
  locked replay goldens. ADR-0019.
- **phase-15**: HTML + JSON reports. Self-contained HTML report (offline-
  enforced); PR-comment upsert via `<!-- sentinelqa:pr-comment -->` anchor;
  inline SVG sparkline trends; Slack Block Kit payload generator. `sentinel
report --latest / --run-id / --format / --open / --explain-score`. ADR-0020.
- **phase-16**: Python SDK at `packages/python-sdk/src/sentinelqa/`. `Sentinel`
  facade with typed sync + `async_<name>` counterparts. Frozen Pydantic
  `AuditResult` model. Agent-message contract (`AGENT_MESSAGE_SCHEMA_VERSION`).
  Public-surface gate: `packages/python-sdk/api-snapshot.json` + unit test
  diff. Lazy-import contract enforced under 600 ms. ADR-0021.
- **phase-17**: CI integration. `engine/ci` ships PRD §21.3 mode presets
  (`fast / standard / full / nightly / release`), diff-aware route selection
  with broad-impact tripwires. `sentinel ci` CLI. GitHub composite Action +
  reusable workflow; GitLab template; PR / MR posters (`urllib`-only).
  TS `sentinel-ts discover` subcommand + `engine.discovery.backends.
playwright_backend.PlaywrightCrawlBackend` lights up the second discovery
  backend (ADR-0010 follow-up #1 closed). ADR-0022.

### Security

- **phase-00..17**: Apache-2.0 licensed, repo privacy locked, gitleaks
  pre-commit + CI scan, no AI co-author trailers, CLAUDE §6 safety boundary
  enforced module-by-module via AST + grep guards.
