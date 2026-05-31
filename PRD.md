# SentinelQA PRD & Architecture Paper

**Product:** SentinelQA  
**Category:** Agentic Playwright-Based Automated Testing Ecosystem  
**Document type:** Product Requirements Document, Technical Architecture, Competitive Audit, Engineering Blueprint  
**Version:** 1.0  
**Date:** 2026-05-27  
**Prepared for:** Product, Engineering, Security, QA, and AI Agent Development Teams

---

## 0. Executive Summary

LLM-generated software has changed the software development bottleneck. The hard problem is no longer producing code; it is verifying that generated code is correct, secure, performant, accessible, maintainable, and production-ready.

**SentinelQA** is a proposed Playwright-first, agentic automated testing ecosystem that works as:

1. A CLI for developers and CI/CD pipelines.
2. A Python SDK for agentic and programmatic usage.
3. A Playwright-native TypeScript runtime.
4. An MCP/LLM-compatible tool interface.
5. A modular QA engine covering functional, regression, API, visual, accessibility, performance, security, chaos, and LLM-code-specific validation.
6. A future cloud dashboard for historical quality analytics, team workflows, test intelligence, and hosted execution.

The product should not be positioned as merely an AI test generator. The strategic category should be:

> **A release-confidence engine for AI-generated software.**

The system should discover an application, infer business-critical flows, generate and execute tests, evaluate risk, produce a quality score, explain failures, repair brittle tests, and optionally propose application fixes through controlled agent workflows.

A previous high-level paper described the opportunity, but it was not complete enough as an implementation PRD. This document fills the missing pieces: feature matrix, architecture, workflows, data model, plugin contracts, agent contracts, safety model, CI/CD integration, CLI/SDK design, report formats, evaluation metrics, MVP scope, roadmap, engineering milestones, and competitive positioning.

---

## 1. Market Context and Competitive Reality

### 1.1 Current market status

The market already contains several AI testing products. SentinelQA is **not first overall** in AI testing. It can still win by being the most complete, open, code-native, Playwright-first, LLM-native product focused specifically on AI-generated software validation.

Important market signals:

- Playwright now explicitly supports reliable automation for tests, scripts, and AI agent workflows, across Chromium, Firefox, and WebKit. It also has official Playwright Test Agents documentation for planner/generator/healer workflows. Sources: Playwright homepage and Playwright Test Agents documentation.
- QA Wolf markets itself as an AI testing platform for fast end-to-end coverage, autonomously mapping, writing, and running Playwright/Appium tests with managed QA support.
- mabl positions itself as agentic AI software testing for teams scaling output with coding agents.
- testRigor positions itself around plain-English, generative-AI-based no-code automation.
- DevAssure O2 positions itself as an autonomous AI testing agent that reads code changes, maps impact, generates end-to-end tests, and executes them in GitHub-driven workflows.
- Autonoma positions itself as an open-source alternative to QA Wolf using AI agents, self-healing, and self-hosted execution.
- BrowserStack and Sauce Labs remain strong execution infrastructure providers for cross-browser and real-device testing.

### 1.2 Key conclusion

Competitors already cover parts of this idea. SentinelQA must not compete only on “AI generates Playwright tests.” That is no longer unique.

SentinelQA must compete on:

1. **LLM-code-specific QA**: detect fake completeness, hallucinated routes, mocked backends, UI-only features, broken generated APIs, missing loading/error states.
2. **Full-stack release confidence**: combine browser, API, accessibility, performance, visual, security, dependency, secrets, and chaos testing.
3. **Open-core, code-native architecture**: CLI + Python SDK + TypeScript Playwright runtime + MCP.
4. **Agent-readiness**: designed to be called by coding agents, not only humans.
5. **Safety-first adversarial testing**: authorized, bounded, auditable security testing.
6. **Evidence-first reports**: every finding includes trace, screenshot, DOM snapshot, network log, stack trace, severity, reproduction, and fix guidance.
7. **Diff-aware testing**: test only what changed when appropriate, while preserving scheduled full-regression coverage.
8. **Policy-driven quality gates**: PRs fail or pass based on configurable business risk, not raw test count.

---

## 2. Safety and Legal Boundary

The original product idea included the word “undetectable.” This must be explicitly rejected as a product feature if it means stealth, anti-bot evasion, bypassing detection, CAPTCHA circumvention, identity spoofing, or unauthorized automation against third-party systems.

### 2.1 Forbidden capabilities

SentinelQA must not include:

- Bot-detection evasion.
- CAPTCHA solving or bypass.
- Fingerprint spoofing for stealth.
- Proxy rotation for evasion.
- Rate-limit bypass.
- Unauthorized vulnerability exploitation.
- Credential stuffing or account takeover testing against real services.
- Automated abuse of third-party platforms.
- Hidden automation intended to appear as a real user outside an authorized test environment.

### 2.2 Allowed alternative: compliant realism

The safe and commercially viable alternative is **compliant realism**:

- Browser automation that mirrors realistic user flows in owned or authorized environments.
- Configurable typing delays and network conditions for reliability testing, not evasion.
- Test identity headers such as `X-SentinelQA-Test-Run`.
- Explicit target allowlists.
- Rate limits.
- Audit logs.
- Safe payloads.
- Staging/local-only destructive testing.
- Proof-of-ownership validation for external domains.
- **Operator-supplied browser sessions** (Phase 31, ADR-0043): for SSO /
  MFA / consumer-LLM web logins, the operator signs in themselves in
  a real browser and SentinelQA captures the resulting Playwright
  `storage_state` into an encrypted local vault (AES-256-GCM, master
  key in the OS keyring). SentinelQA never sees the operator's
  username, password, OTP, or OAuth bearer token. The vault refuses
  to surface a session whose recorded host is not in the active
  target's allowlist, refuses expired entries, and never extends or
  refreshes a session silently. The materialized plaintext session
  file is deleted on run teardown (try/finally), even on crash.

### 2.3 Security testing policy

Security testing must be:

- Authorized.
- Scoped.
- Logged.
- Rate-limited.
- Non-destructive by default.
- Mapped to recognized security testing categories such as OWASP WSTG, OWASP Top 10, DAST, SAST, dependency scanning, secrets scanning, and configuration review.

---

## 3. Product Vision

### 3.1 Vision statement

**SentinelQA helps developers and AI coding agents prove that AI-generated applications are safe enough to ship.**

### 3.2 Product mission

To provide an agentic, Playwright-native, full-stack QA system that automatically discovers, tests, audits, scores, and improves software quality across the entire release lifecycle.

### 3.3 Strategic wedge

The initial wedge should be:

> **Pre-deploy QA for LLM-built web apps.**

Target users are building with Cursor, Claude Code, GitHub Copilot, OpenAI Codex-style agents, Replit, Lovable, v0, Bolt, or other AI coding tools. These users need immediate proof that generated apps actually work.

---

## 4. Target Users and Personas

### 4.1 Solo AI builder

Needs:

- One command to test app.
- Clear explanation of what is broken.
- Simple fix suggestions.
- No enterprise setup.

### 4.2 Startup engineer

Needs:

- CI/CD gate.
- Regression tests.
- Security sanity checks.
- Fast feedback on PRs.
- Playwright-compatible output.

### 4.3 QA engineer

Needs:

- Test plans.
- Coverage mapping.
- Reusable flows.
- Traceable findings.
- Manual review controls.

### 4.4 Engineering manager

Needs:

- Quality score.
- Release risk dashboard.
- Trend analysis.
- Flake rate.
- Team accountability.

### 4.5 AI coding agent

Needs:

- Stable machine-readable API.
- Deterministic command outputs.
- JSON reports.
- Failure reproduction steps.
- Fix verification loop.

---

## 5. Core Jobs To Be Done

1. **Before merge:** determine whether a PR broke critical flows.
2. **Before deploy:** determine whether the app is safe enough to ship.
3. **After LLM generation:** identify generated features that only appear complete.
4. **During development:** generate high-quality Playwright tests from app behavior and code.
5. **During maintenance:** detect and repair flaky or outdated tests.
6. **During security review:** run safe authorized checks and produce actionable findings.
7. **During performance review:** enforce budgets before regressions reach production.
8. **During accessibility review:** catch common WCAG-related issues early.
9. **During API changes:** validate contracts and schema compatibility.
10. **During release governance:** produce a scored evidence report.

---

## 6. Product Principles

1. **Evidence over magic.** Every result must include reproducible evidence.
2. **Playwright-native.** Generated browser tests should be idiomatic Playwright.
3. **Agent-native.** Every human workflow should have an equivalent machine-readable workflow.
4. **Safe by default.** No destructive, stealth, or external scanning without explicit authorization.
5. **Code-first, not only no-code.** Developers should own tests as code.
6. **Open-core adoption.** The CLI and SDK should be easy to adopt without sales friction.
7. **Composable.** Modules should be independently runnable.
8. **Deterministic where possible.** LLMs plan and explain; deterministic runners execute and verify.
9. **Policy-driven.** Teams decide quality gates through config.
10. **Extensible.** Plugin architecture must support new scanners, runners, and reporters.

---

## 7. Product Scope

### 7.1 In scope

- Playwright-based browser automation.
- Test generation.
- Test execution.
- Test repair.
- Functional E2E testing.
- API contract testing.
- Accessibility checks.
- Visual regression.
- Performance budgets.
- Security sanity checks.
- Secrets/dependency scan integrations.
- LLM-code-specific audits.
- CI/CD integration.
- JSON, HTML, JUnit, SARIF reports.
- Python SDK.
- TypeScript runtime.
- MCP-compatible tool server.
- Plugin framework.

### 7.2 Out of scope for MVP

- Native mobile automation.
- Real-device cloud infrastructure owned by SentinelQA.
- Full enterprise dashboard.
- Full human-managed QA service.
- Advanced penetration testing.
- CAPTCHA solving.
- Bot-detection evasion.
- Production attack simulation against third-party systems.

### 7.3 Future scope

The list below was the original future-scope snapshot at MVP definition time. As the project completed the MVP (Phases 00–29) and progressed into the ecosystem expansion (Phases 30–36), several items moved into scope; the remainder stay future-scope with ADR-recorded reasons.

**Moved in-scope post-MVP (Phases 30–36):**

- ✅ Multi-provider LLM support (Gemini, Ollama, Azure OpenAI, Vertex AI, Mistral, Groq, OpenRouter) — Phase 30 (`plans/phase-30-llm-providers/`).
- ✅ Browser-authenticated audits (OAuth + LLM-web app sessions) — Phase 31 (`plans/phase-31-browser-auth/`).
- ✅ Extended security skill catalog (CWE / ATT&CK / OWASP-API-Top-10 mapping) — Phase 32 (`plans/phase-32-extended-security/`).
- ✅ Supply-chain audit (CycloneDX SBOM + OSV + lockfile freshness + container scan + license audit) — Phase 33 (`plans/phase-33-supply-chain/`).
- ✅ Compliance packs (WCAG 2.2, GDPR cookie consent, CCPA Do-Not-Sell, SOC 2 audit-trail) — Phase 34 (`plans/phase-34-compliance/`).
- ✅ Public release engineering — Phase 35 (`plans/phase-35-public-release/`).
- ✅ Ecosystem publish (PyPI, npm, Docker Hub, v1.0.0 GitHub Release) — Phase 36 (`plans/phase-36-publish-ecosystem/`).

**Still future-scope (no phase yet; out of scope until adoption justifies the work):**

- Mobile Appium support — ADR-0033 cloud-boundary precedent applies; revisit post-1.0 if adoption demands it.
- Desktop Electron testing — same.
- Hosted browser execution cloud — ADR-0033, ADR-0036 (cloud delayed until CLI traction).
- Visual AI model — Phase 21 ships pixel + perceptual-hash visual diff; an ML-backed visual diff is future scope.
- Test data management UI — out of scope until the CLI demonstrates need.
- Human-in-the-loop QA marketplace — ADR-0033 precedent.

---

## 8. Competitive Audit

### 8.1 Competitor matrix

| Competitor | Category | Strength | Weakness / gap | SentinelQA differentiation |
|---|---|---|---|---|
| Playwright | Framework | Best-in-class browser automation, multi-browser, traces, strong developer ecosystem | Not a full product, no release-confidence engine by itself | Build intelligence, orchestration, reports, agents, security/perf/a11y modules on top |
| Playwright Test Agents | Agent workflow | Planner/generator/healer pattern validates direction | Mostly focused on test creation and repair | Add full product QA pipeline, scoring, security, performance, CI policy, Python SDK |
| QA Wolf | Managed AI QA | Strong coverage promise, Playwright/Appium, human + AI service | Expensive/service-heavy, less self-hosted/code-native | Open-core, self-serve, SDK-first, LLM-native, modular |
| Autonoma | Open-source AI testing | Similar self-hosted AI testing direction | Appears focused on autonomous E2E generation and healing | Differentiate with full-stack QA modules and LLM-code audit layer |
| DevAssure O2 | AI PR testing agent | Diff-aware impact mapping and GitHub workflow | Less clear open SDK/plugin ecosystem | Compete on extensibility, security/performance/a11y breadth, Python library |
| mabl | Agentic AI testing platform | Mature enterprise testing platform, low-maintenance automation | Commercial platform, less code-native/open-core | Developer-first local CLI and PRD-grade test ownership |
| testRigor | Plain-English testing | Non-technical test creation | Less developer-owned code, possible abstraction limits | Generate real Playwright specs and machine-readable artifacts |
| BrowserStack | Test infrastructure | Real browsers/devices, scale | Not primarily QA intelligence layer | Integrate as execution backend |
| Sauce Labs | Test infrastructure + quality platform | CI integrations, large execution cloud | Less focused on LLM-generated app validation | Integrate as backend, own agentic QA logic |
| Applitools | Visual AI testing | Best-in-class visual validation | Narrower scope | Provide baseline visual, integrate advanced visual providers |
| Cypress | Testing framework | Excellent developer experience | Less agentic/multi-browser aligned than Playwright | Possible import/export, not first runtime |
| Selenium | Legacy standard | Enterprise adoption | Less ergonomic for AI-native workflows | Migration assistant only |

### 8.2 Is someone already doing this?

Partially, yes.

- **QA Wolf** is close on agentic E2E coverage with managed support.
- **Autonoma** is close on open-source autonomous QA Wolf alternative positioning.
- **DevAssure O2** is close on PR-driven autonomous testing.
- **Playwright Test Agents** are close on planner/generator/healer workflow.
- **mabl/testRigor/Testim/Functionize** are mature AI test automation platforms.

No single competitor clearly owns the exact combination of:

1. Open-core CLI.
2. Python SDK for LLM agents.
3. Playwright-native generated code.
4. Full-stack QA modules.
5. LLM-code-specific fake-completeness detection.
6. Safe adversarial testing.
7. Quality scoring and policy gates.
8. MCP-compatible tool interface.
9. Plugin-first local and cloud architecture.

That should be the strategic claim.

---

## 9. Core Product Modules

### 9.1 Discovery module

Purpose: Understand the application surface area.

Inputs:

- Base URL.
- Source code path.
- Routes.
- Sitemap.
- OpenAPI schema.
- GraphQL schema.
- Existing tests.
- README/product docs.
- PR diff.

Outputs:

- Route map.
- DOM interaction map.
- API map.
- Auth map.
- Forms inventory.
- Critical flow candidates.
- Risk map.

Required capabilities:

- Crawl internal links.
- Detect forms and buttons.
- Detect unreachable pages.
- Capture console errors.
- Capture network failures.
- Detect API endpoints called by browser flows.
- Detect missing accessible labels.
- Detect repeated components.
- Detect auth boundaries.

#### 9.1.1 MVP delivery (Phase 05)

The MVP ships in Phase 05 as an HTTP-first pipeline (`engine.discovery`):

- `Crawler` (`engine/discovery/crawler.py`) — httpx-based BFS, robots.txt aware, rate-limited (token bucket), same-host-only by default, transparent UA `SentinelQA/<version>` + `X-SentinelQA-Test-Run: <run-id>` header. Pluggable `CrawlBackend` Protocol.
- `DomMapBuilder`, `FormsInventory`, `ApiDetector`, `AuthBoundaryDetector`, `OpenAPIIngester`, `GraphQLIngester` — produce the typed records the `DiscoveryGraph` carries.
- `build_risk_map` + `RISK_RULES` — ten deterministic, audited rules (login/auth, admin, payment, 5xx, unreachable, form-without-submit, form-without-validation, missing accessible labels, API referenced-only, crawl-failed) summed and clipped to `[0, 1]`. Justifications are recorded per route so the score is fully explainable.
- `sentinel discover --url ...` — replaces the Phase 02 stub. Runs lifecycle steps 1–8 (config → safety → run id → artifact dir → snapshot → discovery), enforces the safety policy before any I/O, writes `discovery.json`, `forms.json`, `api.json`, `auth.json`, `risk.json`, and a human-readable `discovery.report.md` into the run dir.

`discovery.engine: http` is the only backend shipped in Phase 05. The config key is reserved so the Phase 17 Playwright backend (see `plans/phase-17-ci-integration/07-playwright-discovery-backend.md`) plugs in without a schema bump. ADR-0010 records the trade-off: SSR / hydrated / static apps work fully; pure CSR SPAs (empty `<div id="root">`) are out of scope for the MVP and produce an explicit `spa_empty_body` risk note when the body looks empty.

Safety boundary: credentials are read from env vars by name (never inlined in artifacts), the login POST body is never persisted, and `target.allowed_hosts` enforcement runs before any HTTP request.

#### 9.1.2 Playwright backend delivery (Phase 17 task 07)

Phase 17 task 07 lights up the second discovery backend (ADR-0010 follow-up resolved):

- **TS subcommand** — `sentinel-ts discover --config <path|->` (where `-` means stdin) drives Chromium against the target URL. Reads a JSON config describing the crawl shape (base URL, max depth/pages, rate limit, cookies, UA, X-SentinelQA-Test-Run header).
- **JSONL event additions** — `discovery.page` (one per crawled URL with status, content-type, depth, elapsed_ms, html, discovered_links/scripts) and `discovery.endpoint` (one per observed `/api/*` request) added to `packages/shared-schema/ts-events.schema.json` and to the Python parser registry. Existing event ordering preserved (`run.start` first, `run.end` last; the parity fixture asserts this).
- **Python adapter** — `engine.discovery.backends.playwright_backend.PlaywrightCrawlBackend` implements the `CrawlBackend` Protocol. Translation is one-to-one: every `discovery.page` event becomes one `CrawlPage` so downstream detectors (DOM map, forms, API detector) see an identical shape regardless of which backend ran. A pluggable `PlaywrightRunner` Protocol mirrors the Phase 11/12 runner-injection pattern; `SubprocessPlaywrightRunner` is the production driver. Failures bubble up as `SentinelTsNotInstalledError` (mapped to exit code 5) or `PlaywrightDiscoveryError`.
- **Config integration** — `discovery.engine: "playwright"` is now live (no longer reserved). The discover CLI constructs the backend lazily so HTTP-engine runs pay no startup cost; missing-binary errors surface as the typed dependency error.
- **CI lane** — `.github/workflows/ci.yml` adds the `discovery-playwright (gated)` lane, behind `SENTINELQA_HAS_CHROMIUM=1`, that runs `tests/integration/discovery/test_playwright_backend_spa.py` against the CSR SPA fixture at `packages/ts-runtime/fixtures/spa/`.
- **Backend parity test** — `tests/integration/discovery/test_backend_parity.py` runs both backends against the same SSR fixture (served by `pytest_httpserver`) and asserts the produced `CrawlResult` shape is equivalent. The HTTP backend talks to the real httpx-served pages; the Playwright backend consumes a canned JSONL stream representing the same pages so the parity assertion runs without Chromium in the default lane.

### 9.2 Planner module

Purpose: Convert discovery into a test plan.

Outputs:

- Critical flows.
- Smoke tests.
- Regression tests.
- Negative tests.
- Edge cases.
- Security checks.
- Performance checks.
- Accessibility checks.
- Visual snapshots.
- Required fixtures.

Planner must assign:

- Priority: P0/P1/P2/P3.
- Risk: critical/high/medium/low.
- Confidence.
- Test type.
- Required auth role.
- Required data state.

#### 9.2.1 MVP delivery (Phase 06)

Phase 06 ships the planner as `engine.planner`:

- **Deterministic core** — `DeterministicPlanner.plan(graph, risk, config, run_id=…)` produces a `TestPlan` from any `DiscoveryGraph` + `RiskMap`, with no network calls and no LLM dependency. Same inputs → same plan modulo IDs (verified by `tests/golden/planner/fixture-app.plan.json`).
- **Rules engine** — every route gets a smoke flow; every form gets a functional flow (P0 on login/signup/payment/admin routes, P1 otherwise); every form without a submit handler is tagged `llm_audit_candidate`; every API endpoint becomes a contract test (executed in Phase 22); every auth-required route gets an auth-boundary flow.
- **Named flow extractors** — login, signup, logout, password reset, CRUD, search/filter/sort, admin, role, file upload/download, payment sandbox, notification callback. Each extractor publishes its own confidence; below 0.5 the flow carries the `confidence_low` tag.
- **Optional LLM augment** — `planner.llm.enabled=false` by default. When enabled, an `LlmPlanner` adapter proposes additional flows that are re-validated through Pydantic, capped by `max_proposals`, gated by a per-run USD budget (`max_usd_per_run`, default $0.50), and merged with `source="llm"` so downstream modules can distinguish them. The locked system prompt lives at `engine/planner/llm_prompts/planner.v1.md`; bumping the version requires a new ADR (ADR-0011).
- **Providers shipped** — `openai_planner.py` (Chat Completions, `response_format=json_object`) and `anthropic_planner.py` (Messages API). Both speak HTTP directly via `httpx`; no vendor SDK is imported. A subclass interface (`HttpLlmProviderBase`) makes adding a third provider a small unit of work.
- **Multi-provider extension (Phase 30, ADR-0042)** — Phase 30 introduced the canonical `engine.llm.LlmProvider` Protocol and seven additional HTTP-only adapters: `gemini` (Google AI Studio), `ollama` (local, offline default), `azure_openai`, `vertex` (Google Vertex AI, RS256 JWT exchange via the PyCA `cryptography` library), `mistral`, `groq`, `openrouter` (gateway). Plus the canonical `anthropic` + `openai` adapters at `engine/llm/providers/*.py`. The Phase-06 planner facade and the canonical surface co-exist: existing call sites are unchanged; new consumers (healer, future modules) implement once against `LlmProvider`. The full ten-provider matrix is enumerable via `sentinel llm list` and reachability-probed via `sentinel llm doctor`.
- **Safety boundary** — provider credentials come from env vars by name only; the LLM payload contains route paths and counts, never form values, headers, cookies, query strings, env-var values, or source code (`build_graph_summary()` is the single point of redaction).
- **CLI** — `sentinel plan --url …` runs lifecycle steps 1–9 and writes `plan.json` + `plan.md`. `sentinel plan --from-discovery <run-dir>` re-uses an existing `discovery.json`/`risk.json` instead of crawling again. `--llm/--no-llm` overrides `planner.llm.enabled` for the run.
- **Artifacts** — `plan.json` (schema envelope at `packages/shared-schema/plan.schema.json`) and `plan.md` (deterministic Markdown summary). `audit.log` gains `plan.start`, `plan.llm.usage`, `plan.llm.budget_exceeded`, and `plan.complete` entries.

### 9.3 Generator module

Purpose: Generate Playwright tests, fixtures, and helper files.

Generated files:

- `tests/sentinel/*.spec.ts`
- `tests/sentinel/fixtures/*.ts`
- `tests/sentinel/pages/*.ts`
- `tests/sentinel/setup/*.ts`
- `sentinel.generated.plan.md`

Rules:

- Prefer role-based locators.
- Prefer accessible names.
- Avoid brittle CSS selectors unless no semantic selector exists.
- Use stable test IDs only if configured.
- Include explicit assertions.
- Include negative tests.
- Include cleanup.
- Avoid sleeps except where justified.
- Use trace mode on failure.

#### 9.3.1 MVP delivery (Phase 07)

`engine.generator` ships the Phase-07 MVP wired behind `sentinel generate`. The implementation is governed by ADR-0012.

- **Templates.** Fourteen Jinja2 templates under `engine/generator/templates/`: `smoke`, `login`, `signup`, `logout`, `crud_create`, `crud_read`, `crud_update`, `crud_delete`, `role_boundary`, `payment_sandbox`, `file_upload`, `api_contract`, `a11y_axe`, `perf_budget`. Each emits one or more `sentinelTest` blocks importing `@sentinelqa/ts-runtime/playwright`, with semantic locators, explicit assertions, and `{ tag: [...] }` test tags reflecting the flow's priority + planner-emitted tags.
- **Renderer.** `engine.generator.render.render_template(name, ctx)` uses Jinja2 with `StrictUndefined` so missing context vars raise `RenderError`. Templates MUST include `{{ banner }}` at the top; the banner marker is the basis for the writer's hand-edit guard. Two regex filters (`regex_literal` escapes literal labels, `regex_pattern` passes alternation patterns verbatim) keep the template authors out of escape-hell.
- **Page objects.** `engine.generator.page_objects.generate_page_objects` emits one `<RouteName>Page.ts` per route that either appears in ≥ 2 flows or has ≥ 3 interactive elements. Each page object encapsulates semantic locators (one accessor per discovered element with an accessible name + role), a `goto()` action, and a `verify()` assertion against the route's anchor landmark. Elements without an accessible name are dropped (recorded in `GeneratedPageObject.skipped_elements`).
- **Fixtures.** `engine.generator.fixtures.generate_fixtures` emits four files when the corresponding config is provided:
  - `tests/sentinel/fixtures/auth.ts` — `authenticatedTest` extension that performs login once per worker. Credentials are read from `auth.username_env` / `auth.password_env`; the env-var **names** are referenced in the source, never the values.
  - `tests/sentinel/fixtures/data.ts` — opt-in `freshUser` fixture that POSTs to the config-named (or heuristically chosen) user-create endpoint. The runtime guard fails closed unless `security.mode == "authorized_destructive"`.
  - `tests/sentinel/setup/global-setup.ts` and `tests/sentinel/setup/global-teardown.ts` — Playwright lifecycle hooks.
- **Brittleness audit.** `engine.generator.locator_strategy.audit_specs` shells out to `sentinel-ts audit-locators --file <path>` (new in Phase 07, added to the TS CLI). The Phase-04 `auditLocatorBrittleness` rule set is the single source of truth. `sentinel generate` runs the audit BEFORE writing any spec; findings abort the write and exit code 6. `--no-audit` skips it for local debugging only.
- **Plan markdown.** `engine.generator.plan_md.render_generated_plan_md` emits `tests/sentinel/sentinel.generated.plan.md` with a deterministic summary (counts, per-flow table, file list) and a diff-vs-prior section when a previous plan.md exists.
- **Writer.** `engine.generator.writer.write_generated_files` is the only path that writes generated files. It detects SentinelQA-managed files via the banner marker in the first 4 KiB. Hand-owned files (no marker) raise `OverwriteError` (exit 6) unless `sentinel generate --force` is passed. Writes are atomic (temp file + `os.replace`).
- **Pipeline.** `engine.generator.pipeline.GeneratorPipeline.generate` takes a `TestPlan` + `DiscoveryGraph` and returns a `GenerationResult` carrying every `GeneratedFile` (path + content + kind). The pipeline never touches the filesystem; the CLI does.
- **CLI.** `sentinel generate --url <URL>` (or `--from-plan <path> --from-discovery <dir>`) replaces the Phase-02 stub. Options: `--out tests`, `--source .`, `--force`, `--no-tsc`, `--no-audit`, `--json`, `--quiet`, `--dry-run`. Exit codes: `0` on success, `4` for unsafe targets (safety policy refusal before any write), `6` for audit failures or hand-owned file collisions.
- **Determinism.** Re-running `sentinel generate --from-discovery <dir>` produces byte-identical files. Spec filenames are derived from `extractor + flow.name` slug + (when needed) a stable disambiguator from discovery IDs (`form:FRM-*` / `endpoint:API-*` tags). Auto-generated planner IDs (`FLW-*`, `RUN-*`) never appear in spec source or filenames.
- **Safety boundary.** Generated tests never embed credentials. The data fixture refuses to run unless `security.mode == "authorized_destructive"`. The generator never produces stealth, evasion, or rate-limit-bypass code.

### 9.4 Runner module

Purpose: Execute tests locally, in CI, or through remote providers.

Execution targets:

- Local Playwright.
- GitHub Actions.
- GitLab CI.
- Docker.
- BrowserStack.
- Sauce Labs.
- Future Sentinel Cloud.

Runtime artifacts:

- Trace zip.
- Screenshots.
- Videos.
- HAR files.
- Console logs.
- Network logs.
- DOM snapshots.
- JSON result.
- JUnit result.

#### 9.4.1 MVP delivery (Phase 08)

The MVP ships two execution targets — **local Playwright** and **Docker** — that share a single contract. The other PRD §9.4 targets (GitHub Actions, GitLab CI, BrowserStack, Sauce Labs, Sentinel Cloud) sit on top of this same contract in Phase 17 / Phase 25.

- **Shipped surface.** `engine.runner` exposes `LocalRunner` and `DockerRunner` (matching `RunnerInvocation → RunnerOutcome`), the JSONL → typed `RunnerOutcome` aggregator (`engine.runner.results.aggregate`), strict quarantine (`engine.runner.quarantine.Quarantine`), deterministic sharding (`engine.runner.sharding.split_shard` + `merge_outcomes`), and the wire envelope `module-results/<module>.json` versioned by `MODULE_RESULTS_SCHEMA_VERSION = "1"`.
- **Local runner.** Spawns `sentinel-ts run --input <run-config.json>` via `asyncio.create_subprocess_exec`, streams stdout JSONL through the Phase-04 bridge (`engine.orchestrator.ts_bridge.stream_events`), aggregates events into a typed `ModuleResult`, persists `module-results/<module>.json`, and writes a redacted `logs/runner.<module>.log` with the captured stderr regardless of exit code. SIGINT propagates as `SIGINT → SIGTERM → SIGKILL` with a configurable grace window. Missing `sentinel-ts` exits 5 (`EXIT_DEPENDENCY_MISSING`).
- **Docker runner.** Same contract; pinned to `mcr.microsoft.com/playwright:v1.49.0-jammy` (matches `@playwright/test@1.49.0`). The Dockerfile lives at `apps/cli/sentinel/runner/docker/Dockerfile.runner`; `make build-runner-image` is the canonical local build. The container is launched `--rm --init --network bridge` with `host.docker.internal:host-gateway` aliased so localhost targets work, source mounted read-only, and the run dir mounted writable. No `--privileged`, no Docker socket, no `--cap-add`. `SafetyPolicy.enforce` is re-invoked inside the runner before container launch.
- **Retry + quarantine.** Pass-on-retry is recorded as `flaky`; `RunnerOutcome.flake_rate = flaky / (total − skipped)` and the CLI fails 1 (`EXIT_QUALITY_GATE_FAILED`) when it exceeds `policy.max_flake_rate`. The quarantine list (`runner.quarantine.path`, default `tests/sentinel/.quarantine.yaml`) is a strict YAML list of `{test_id, reason, expires_at, issue_url}` entries; the loader rejects unknown fields, expired entries, entries past `max_age_days` in the future, and non-URL `issue_url` values. Quarantined tests run, but their failures do not block the module status.
- **Sharding.** `runner.shards = "N/M"` (or `--shard N/M` on the CLI) splits specs deterministically: `sha1(posix_path) % total`. Unions across all shards cover the input set exactly; `merge_outcomes` deduplicates `TestExecution` records by `test_id`, picks the worst module status (`errored > failed > incomplete > skipped > passed`), and preserves the first non-None environment. Workers are configurable via `runner.workers` (`auto` resolves to `os.cpu_count()`).
- **CLI.** `sentinel test` accepts `--path`, `--grep`, `--workers`, `--shard`, `--browser`, `--docker`, `--retries`, `--with-generate`, `--url`, `--module`, plus the global `--config / --ci / --json / --quiet / --verbose`. The lifecycle steps actually exercised by `sentinel test` are config-load → safety-policy → quarantine-load → optional generate → spec discovery → runner spawn → aggregate → write `module-results/<module>.json`. `--with-generate` invokes the Phase-05/06/07 chain (discovery → planner → generator) before running the runner; without it the user runs `sentinel generate` separately. Exit code grid: `0` (passed), `1` (flake-rate gate violation), `2` (invalid config or no matching specs), `4` (`UnsafeTargetError`), `5` (`sentinel-ts` missing), `6` (runner spawn/execution error).
- **Determinism contract.** Each module's `run-configs/<module>.json` and `module-results/<module>.json` are written atomically. Stderr lands in `logs/runner.<module>.log`. The aggregator never crashes on partial streams — a missing `run.end` event flips `module_result.status` to `incomplete` and `RunnerOutcome.incomplete=True`. ADR-0013 owns the rationale.
- **Safety boundary.** The runner only allows targets the safety policy already approved (CLAUDE.md §6, PRD §2); the Docker runner re-checks the policy before container launch. The runner never spawns sibling containers, never mounts the Docker socket, and never adds `--privileged`/`--cap-add` flags.

### 9.5 Analyzer module

Purpose: Interpret failures.

Failure categories:

- App bug.
- Test bug.
- Environment failure.
- Flake.
- Data setup failure.
- Auth failure.
- API failure.
- Performance regression.
- Security finding.
- Accessibility violation.

Analyzer output:

- Root cause hypothesis.
- Confidence.
- Evidence.
- Reproduction steps.
- Suggested fix.
- Whether to retry.
- Whether to quarantine.

#### 9.5.1 MVP delivery (Phase 09, ADR-0014)

The Phase 09 analyzer ships the deterministic core for every PRD §9.5 output. The LLM explainer is opt-in and never authoritative.

- **Inputs.** The analyzer consumes one `engine.analyzer.models.FailureSignal` per failed (`failed` / `timed_out` / `flaky`) test. Signals are built via `engine.analyzer.signals.build_failure_signal(execution, *, events=..., module=..., route=..., fixture_failed=..., error_name=..., attempts=...)` from the runner's `TestExecution` (ADR-0013) plus the captured step / network / console events. A second builder, `build_module_error_signal(module=..., exc_type=..., exc_message=...)`, lifts the lifecycle's broad `except Exception` (CLAUDE.md §10) into the same signal shape so module-level errors are categorized with the same vocabulary as per-test failures.
- **Categorization (`engine.analyzer.categorize.categorize`).** An ordered rule set of eleven named rules emits a `FailureClassification` with the closed-set category (`app_bug` / `test_bug` / `environment_failure` / `flake` / `data_setup_failure` / `auth_failure` / `api_failure` / `performance_regression` / `security_finding` / `accessibility_violation`) plus `unknown` for signals that match no rule. Every matching rule is preserved as a `secondary` entry. Rules are intentionally narrow (no "any 5xx = app_bug" sweep); under-claim is preferred to mis-blame. Module-level errors are categorized by `categorize_module_error(module=..., exc_type=..., exc_message=...)` and surfaced on `ModuleOutcome.error_category` / `error_confidence` / `error_rationale` / `error_type`.
- **Hypothesis (`engine.analyzer.root_cause.hypothesize`).** Per-category templates interpolate a redaction-safe snippet (URLs stripped of query/fragment + clipped at 80 chars, error messages clipped at 200 chars) into a one-to-two-sentence `RootCauseHypothesis` with the classification's confidence (never re-inflated) and a fixed ordered `next_actions` checklist per category. Hypothesis text is hard-clipped at 1024 chars regardless of input size.
- **Reproduction (`engine.analyzer.repro.reproduction`, `build_repro_spec`).** `reproduction(signal, *, auth_env_vars=..., base_url=...)` returns the human-readable steps: open the trace, visit the route, authenticate via `*_env` references (never literal credentials per CLAUDE §33), replay each captured step, observe expected vs actual. `build_repro_spec(signal, *, base_url, finding_id, auth_env_vars=...)` emits a minimal Playwright TS spec gated by the `// SENTINELQA AUTO-GENERATED REPRO SPEC` banner; auth pulls from `process.env["NAME"]`; the assertion is a TODO the user replaces. The spec is a starting point, not a self-healing replay.
- **Retry / quarantine (`engine.analyzer.retry_decision.should_retry`).** Returns a typed `RetryDecision` (`retry` | `quarantine_candidate` | `no_action`). Flake and environment failures → retry. Auth-fixture failure → no_action (config-bound). Auth surfaced mid-test → retry (distinguish session timeout from a true block). App / API / security / a11y / performance / data-setup → no_action (deterministic). Test bug → no_action on the first attempt; `quarantine_candidate` once we've already retried or the optional `FailureHistory` shows recurring failures against a healthy app. A hard cap of two auto-retries applies regardless of category (CLAUDE §23).
- **Pipeline (`engine.analyzer.pipeline.Analyzer`).** `Analyzer().analyze(signals, context=AnalyzerContext(auth_env_vars=..., base_url=..., history_by_test=...))` runs every stage in order, sorts results by `test_id`, and optionally appends a one-sentence `llm_refinement` from a configured explainer. Per-result output is `AnalyzerResult { test_id, classification, hypothesis, reproduction, retry_decision }`.
- **LLM explainer adapter.** `engine.analyzer.llm_explainer` defines an `LlmExplainer` Protocol, a `NullLlmExplainer` default, and two HTTP-only provider adapters (`OpenAiLlmExplainer`, `AnthropicLlmExplainer`) — same shape as the planner adapter (ADR-0011). The locked prompt is `engine/analyzer/llm_prompts/explainer.v1.md` (`PROMPT_VERSION = "1"`); bumping it requires a new ADR. Provider responses are strictly validated (`{ "refinement": "<= 400 chars" }`); malformed responses are dropped silently and the deterministic hypothesis is preserved. Spend is bounded by `analyzer.llm.max_usd_per_run` (default $0.25). The feature is OFF by default (`analyzer.llm.enabled: false`); with the flag off, no LLM is constructed, no HTTP client is opened, and the analyzer is fully deterministic.
- **Multi-provider extension (Phase 30, ADR-0042).** Same nine-provider matrix as §9.2.1 — the canonical `engine.llm.LlmProvider` Protocol replaces the per-caller `LlmExplainer` for new code. The Phase-09 facade continues to use the original two-provider adapter tree for backwards-compatibility.
- **Safety boundary.** No credentials are ever inlined in repro output. The LLM summary clips fields and never re-includes raw cookies or `Authorization` headers (the caller pre-redacts per CLAUDE §33). The explainer respects the same env-var-name convention as `auth.*_env`. The deterministic path is identically reachable in air-gapped environments.

ADR-0014 owns the rationale and alternatives.

### 9.6 Healer module

Purpose: Repair tests safely.

Allowed repairs:

- Locator update.
- Wait condition improvement.
- Fixture update.
- Test data cleanup.
- Assertion stabilization.
- Page object refactor.

Not allowed automatically:

- Weakening assertions without review.
- Ignoring failures.
- Removing tests.
- Disabling security checks.
- Changing production code unless explicitly requested.

#### 9.6.1 MVP delivery (Phase 20)

Phase 20 ships the conservative MVP (ADR-0025) backed by three
deterministic proposers and a banner-aware apply gate. The Healer is
signal-driven — it consumes the Phase-04 locator descriptor, the
Phase-05 discovery DOM map, and the spec source on disk; no new
runner harness is required.

- **Module package.** `engine/healer/` with:
  - `engine.healer.Healer.propose(failure, inputs, *, context)` —
    facade returning a tuple of typed `RepairProposal` records,
    sorted by `(kind, id)` for determinism.
  - `engine.healer.locator_repair.propose_locator_repair` — scores
    `DomCandidate` records against a `LocatorDescriptor`. Exact
    role + name + landmark → confidence `0.95`; same role + name
    (different landmark) → `0.9`; fuzzy name match (similarity ≥
    0.8) in same landmark → `0.75` (different landmark → `0.7`);
    role-only → `0.5`. Anything below the configured
    `auto_apply_threshold` (default `0.9`) carries
    `requires_human_review=True`.
  - `engine.healer.wait_repair.propose_wait_repair` — replaces
    `await page.waitForTimeout(...)` with reliance on the following
    `await expect(...).toBe* / toHave* / toEqual / toMatch / toContain`
    Playwright assertion. Confidence `0.9` for `toBeVisible` /
    `toHaveText`; `0.6` for other matchers; `0.3` when no following
    assertion is found and the proposal degrades to a documented
    removal.
  - `engine.healer.fixture_repair.propose_fixture_repair` — for
    `seededRecord` failures of kind `missing_entity` (confidence
    `0.85`) emits a structured re-seed proposal; for
    `contract_drift` (confidence `0.7`) emits a
    `sentinel generate --from-discovery` proposal. The Healer
    never mutates a database.

- **Wire format.** `RepairProposal` is a strict superset of the
  Phase-01 `RepairSuggestion` (`id`, `target_test`, `original`,
  `proposed`, `confidence`, `reason`, `evidence`,
  `requires_human_review`, `schema_version`) plus
  `kind ∈ {locator, wait, fixture, assertion}`, `target_test_line`,
  `unified_diff`, and an optional `descriptor`. Locked at
  `packages/shared-schema/repair-proposal.schema.json` (Draft
  2020-12, `x-sentinelqa-schema-version: "1"`). Persisted under
  `<run-dir>/healer/<id>.json` plus an aggregate
  `<run-dir>/healer/index.json` summarizing counts by kind and the
  per-proposal `id / kind / confidence / target_test /
  requires_human_review`.

- **Assertion-weakening guard.** `engine.healer.diff.assert_no_assertion_weakening`
  counts structural Playwright assertions (`expect(`, `.toBe*`,
  `.toHave*`, `.toEqual`, `.toMatch`, `.toContain`) after stripping
  `//` line comments and `/* ... */` block comments. Any decrease
  raises `AssertionWeakeningError` unless `allow_weaken=True`. Every
  proposer calls the guard unconditionally; a future assertion-
  stabilization proposer must pass `allow_weaken=True` AND the CLI
  must require `--allow-weaken` to apply such a proposal (CLAUDE.md
  §23).

- **Banner-aware apply.** `engine.healer.banner.detect_banner_status`
  inspects the head of a spec for the Phase-07 banner
  (`// SENTINELQA AUTO-GENERATED`) and a `// generated_at: <ISO>`
  timestamp. Missing banner → hand-edited. Banner present but file
  mtime is more than 5 seconds after the recorded `generated_at` →
  hand-edited. Hand-edited specs are refused regardless of
  `auto_apply` mode.

- **Auto-apply gating.** `engine.healer.gating.decide_auto_apply`
  returns the typed `AutoApplyDecision`. `off` (default) never
  applies; `safe` applies `locator` and `wait` repairs at or above
  threshold; `aggressive` adds `fixture` and `assertion` repairs
  (the latter still require `--allow-weaken`). The decision's
  one-sentence `reason` is logged verbatim to the run's
  `audit.log` on apply and on skip (CLAUDE.md §11).

- **`sentinel fix` CLI** (replaces the Phase-02 stub).
  Options: `--latest / --no-latest`, `--run RUN-...`,
  `--apply none|safe|aggressive`, `--dry-run`, `--allow-weaken`,
  `--review-only`, `--threshold 0.5..1.0`. Default behavior is
  review-only (`--apply none` prints each proposal as a unified
  diff). Exit codes 0 / 2 (config or CLI usage error, including
  unknown `--run` id or unknown `--apply` value) / 6 (one or more
  proposed diffs failed to apply cleanly). JSON mode (`--json`)
  emits a single-line summary `{run_dir, count, applied, reviewed,
  skipped, errors}` and remains stdout-pure (CLAUDE.md §13).

- **MCP integration.** `sentinel.suggest_fix` (Phase 18) now
  surfaces persisted healer proposals for the finding's target file
  alongside the module's deterministic `recommendation` /
  `suggested_fix`. `sentinel.verify_fix` (PRD §16.4) already
  confirms the agent's apply via re-running the audit — Phase 20
  wires the loop end-to-end without changing the agent-envelope
  wire format. The SDK's `Sentinel.verify_fix` method still defers
  apply-fix to the agent; SentinelQA is the verifier.

- **Config block.** New `healer:` section in
  `sentinel.config.yaml`:

  ```yaml
  healer:
    auto_apply: "off"            # off | safe | aggressive
    auto_apply_threshold: 0.9     # 0.5..1.0
  ```

- **Analyzer ↔ Healer routing.** `engine.analyzer.pipeline.is_healer_candidate(result)`
  returns `True` only for `classification.category == "test_bug"`
  with confidence ≥ `0.5`. Callers (CLI / SDK / orchestrator) read
  the analyzer's published `AnalyzerResult` and invoke the Healer
  for the test_bug candidates; the Analyzer itself stays a
  pure-function pipeline.

CLI / SDK contracts in §13 / §14 are unchanged beyond the
`sentinel fix` command landing. ADR-0025 owns the rationale.

### 9.7 Reporter module

Purpose: Generate human and machine-readable reports.

Formats:

- HTML.
- JSON.
- JUnit XML.
- SARIF.
- Markdown.
- GitHub PR comment.
- Slack summary.

Report must include:

- Quality score.
- Pass/fail summary.
- Risk summary.
- Module scores.
- Critical blockers.
- Screenshots/traces.
- Reproduction steps.
- Suggested fixes.
- Trend if history exists.

#### 9.7.1 MVP delivery (Phase 15)

Phase 03 shipped the machine-readable envelopes
(`run.json`/`findings.json`/`score.json`/`junit.xml`/`sarif.json`/`report.md`)
and the dispatcher that ties them to `RunLifecycle.generate_reports`.
Phase 15 ships the **human-readable** layer:

- **HTML report (ADR-0020, §3.1).** `engine.reporter.html_writer.write_html`
  renders a self-contained `report.html` from a Jinja2 template
  (`engine/reporter/html/template.html.j2`) with inline CSS / JS
  (≤ 30 KB each). Header (score badge + decision badge + run id +
  target + duration), summary panel, critical-blocker section pinned
  at top, full findings table with severity / module / search filters,
  per-module result cards, lazy-loaded evidence drawer, audit-trail
  view, optional trend overlay, footer with config digest + schema
  versions + companion-artifact links. Theme: light + dark via
  `prefers-color-scheme`. `HTML_REPORT_SCHEMA_VERSION="1"` locks the
  envelope; bumps require an explicit golden update. **Offline by
  design (CLAUDE §41):** no `<link>`/`<script>`/`<img>`/`<iframe>`
  references an external host. The drift guard is
  `tests/integration/reporter/test_html_self_contained.py`. The HTML
  also passes our own structural a11y checks
  (`tests/integration/reporter/test_html_self_a11y.py`).
- **PR comment (ADR-0020, §3.2).** `engine.reporter.pr_comment.render_pr_comment`
  returns GitHub-flavored Markdown that includes the score badge,
  release decision, top-5 critical findings, changed flows (diff-aware
  mode), module summary, artifact links, and suggested next steps.
  All user-controlled strings flow through `md_escape`. The comment
  begins with the literal HTML-comment anchor
  `<!-- sentinelqa:pr-comment -->` so the Phase-17 GitHub Action can
  upsert (edit-in-place) the same comment on every push instead of
  spawning new ones. Output is capped at GitHub's 65 535-char comment
  limit; the truncator appends a "report truncated" notice and a link
  to `report.html`.
- **Trends (ADR-0020, §3.4).** `engine.reporter.trends.compute_trends`
  walks `.sentinel/runs/<id>/` newest-first, derives a total-score
  series, per-module pass-rate series, and the top recurring finding
  IDs across the last 10 runs (configurable via `history_depth`).
  Sparklines are inline SVG (no JS chart library). The trends section
  is hidden when fewer than two prior runs exist (PRD §9.7 — "trend
  if history exists"). No external storage; cloud history is a
  future-phase opt-in (PRD §41 — no telemetry).
- **Audit-trail view (ADR-0020, §3.5).** `engine.reporter.audit_view`
  normalizes the redacted `audit.log` JSONL into a typed
  `AuditEntry` sequence; the HTML report embeds the entries inside a
  collapsible section with level / module filters. Malformed lines
  are dropped silently (the report is best-effort, never blocked by a
  corrupted log).
- **Slack summary (ADR-0020, §3.6).** `engine.reporter.slack.render_slack_payload`
  returns a Slack Block Kit JSON dict (header, summary section with
  six metadata fields, optional top-blockers section, context, optional
  "open report" actions block). Phase 15 generates the payload only —
  Phase 25 owns posting it. The output is validated against the
  vendored subset schema at
  `packages/shared-schema/external/slack-block-kit.schema.json`.
- **`sentinel report` CLI (ADR-0020, §3.8).** Replaces the Phase-14
  stub for non-explain calls. Subcommands: `sentinel report --latest`,
  `sentinel report --run-id RUN-...`, `sentinel report --format
  html,json,sarif,junit,md`, `sentinel report --open` (browser open,
  skipped in CI), `sentinel report --explain-score` (Phase-14 path
  preserved). Re-render reads the persisted artifacts and rewrites
  the requested formats; the re-render is **idempotent** (same inputs
  → byte-identical outputs) and never writes audit-log entries (the
  audit log is a one-shot record of the original run's decisions per
  CLAUDE §11). Exit codes: 0 success, 2 config error (missing run,
  empty format filter), 7 reserved for internal errors.
- **Wire-format additions:** `HTML_REPORT_SCHEMA_VERSION="1"` (HTML
  template), Slack Block Kit subset schema (vendored upstream); both
  are versioned per ADR-0020.
- **Coverage gate:** `engine.reporter` package ≥ 85 % (ADR-0020 hits
  96 % in CI).

Phase 17 wires `sentinel report` into the GitHub Action (PR-comment
posting); Phase 25 wires the Slack payload into the actual Slack
client. Until then, both payloads ship as artifacts only.

---

## 10. Testing Capabilities

### 10.1 Functional E2E testing

Required flows:

- Login.
- Signup.
- Logout.
- Password reset.
- CRUD flows.
- Search/filter/sort.
- Multi-step forms.
- Settings flows.
- Role-based flows.
- Admin flows.
- File upload/download.
- Notification/email link flows.
- Payment sandbox flows.

#### 10.1.1 MVP delivery (Phase 10)

The functional module ships in Phase 10 as the first concrete `SentinelModule` (CLAUDE §9, ADR-0015). Key implementation contracts:

- **Module package:** `modules/functional/` houses `FunctionalModule(SentinelModule)`. Importing the package auto-registers the module with the process-wide `ModuleRegistry` so `sentinel audit` and `sentinel functional` both pick it up without bespoke wiring.
- **Lifecycle:** `validate_prerequisites → plan → execute → collect_evidence → emit_findings → emit_metrics → summarize`. The seven steps are owned by the module; the orchestrator calls `module.run(ctx)`. The sentinel-ts probe lives inside `execute()` so projects that haven't generated specs yet (no work to do) report `skipped`, not `errored`.
- **Findings translation:** failed/timed-out `TestExecution` records become typed `Finding`s with PRD §20 evidence via `engine.modules.base.build_finding_from_failed_test`. Quarantined tests (Phase 08.04) never produce findings; the quality gate is unaffected by their result.
- **Tag conventions (ADR-0015 §6):** every generated spec emits, in order, `@p0..p3`, `@module:<name>`, `@flow:<extractor>`, `@risk:<level>`, plus any planner-attached, ID-stripped tags. The `@module:` value is mapped from the planner extractor (Phase 06) — most flows land on `functional`, with `api.contract` → `api`, `a11y` → `a11y`, `perf` → `performance`.
- **Slice modes:** `sentinel functional --mode smoke|standard|full` resolves a Playwright `--grep` value via `modules.functional.tags.TagSelection`. `smoke → @p0`, `standard → @p0|@p1`, `full → no filter`. Combined with `--grep <user>` the two are intersected. The TS runner accepts a new `grep?: string` field on the run-config schema and forwards it to `playwright test --grep <value>`.
- **CLI:** `sentinel functional` runs the canonical `RunLifecycle` restricted to the functional module. Options: `--url`, `--mode`, `--grep`, `--workers`, `--shard`, `--retries`, `--spec-root`, plus the global `--config / --ci / --json / --quiet / --verbose`. Exit codes follow the standard grid: 0 (passed, no findings ≥ high), 1 (quality gate failed), 2 (config / shard / mode error), 4 (unsafe target), 5 (runner binary missing), 6 (runner error).
- **Lifecycle hand-off:** `RunLifecycle.execute(... module_options={"functional": {...}})` threads per-module options into `ModuleContext.options`. `RunLifecycle.last_context` exposes the most recent context so the CLI / SDK (Phase 16) can read typed findings + module results without a disk round-trip.
- **Safety:** the payment_sandbox template uses Stripe's published `4242 4242 4242 4242` test card and gates the test on `SENTINEL_PAYMENT_SANDBOX=1`; production card numbers never appear in generated specs (CLAUDE §6, PRD §2). Login specs read credentials from env-var-named slots only (CLAUDE §33). Fixtures (`packages/ts-runtime/fixtures/sample-app[-broken]/`) are dev-only and never distributed as examples.

### 10.2 Regression testing

Modes:

- Full regression.
- Smoke regression.
- Diff-aware regression.
- Scheduled nightly regression.
- Pre-deploy regression.

### 10.3 API testing

Capabilities:

- OpenAPI import.
- GraphQL schema import.
- Contract validation.
- Response schema validation.
- Authenticated API calls.
- Negative tests.
- Pagination tests.
- Rate-limit tests in authorized environments.
- Error-shape validation.
- Backward compatibility checks.

#### 10.3.1 MVP delivery (Phase 22, ADR-0027)

The `modules/api/` package ships seven check kinds, each addressable
individually via `api.enabled_checks` and via `sentinel api --checks`.
All HTTP traffic is Python-driven through `httpx` and goes through
`engine.policy.safety.SafetyPolicy.enforce` before the first request:

- **`contract`** — for each operation in the supplied OpenAPI 3.x doc,
  send a safe-method probe (GET / HEAD / OPTIONS only) and validate
  the response status, content-type, and JSON body against the
  documented schema. Findings: `CONTRACT-STATUS`,
  `CONTRACT-CONTENT-TYPE`, `CONTRACT-INVALID-JSON`,
  `CONTRACT-MISSING-FIELD`, `CONTRACT-SCHEMA`, `CONTRACT-NETWORK`.
  GraphQL contract validation runs in the same check via
  `POST <api.graphql_endpoint>` and emits `GRAPHQL-STATUS`,
  `GRAPHQL-CONTENT-TYPE`, `GRAPHQL-INVALID-JSON`, `GRAPHQL-SHAPE`,
  `GRAPHQL-RESOLVER-ERROR`, `GRAPHQL-NULL-NON-NULL`,
  `GRAPHQL-MISSING-FIELD`, `GRAPHQL-NETWORK`. GraphQL subscriptions
  are detected in the SDL but not probed (deferred to Phase 23).
- **`negative`** — for each request body schema, generate a small,
  bounded variant catalogue: missing-required field, wrong-type,
  out-of-range integer, and oversized-string (≤
  `api.negative_max_payload_kb - 1` KB). Findings:
  `NEGATIVE-VALIDATION-GAP` (high — server accepted bad input),
  `NEGATIVE-SERVER-ERROR` (high — 5xx on bad input).
- **`auth`** — for each authenticated operation (or each
  `api.routes` entry when no OpenAPI doc is loaded), send three
  probes: anonymous, expired-token sentinel
  (`Bearer expired-token-sentinelqa-probe`), and cross-user (one
  per `api.auth_test_users` entry whose `token_env` is set).
  Findings: `AUTH-UNAUTHORIZED-ANONYMOUS` (critical),
  `AUTH-UNAUTHORIZED-EXPIRED_TOKEN` (high),
  `AUTH-UNAUTHORIZED-CROSS_USER:<label>` (high).
- **`latency`** — dedup-only. Phase 12 perf owns
  `performance.budgets.api_p95_ms` enforcement (category
  `perf/api_latency`). The API module's latency check therefore
  always returns `skipped=True` with a `skip_reason` naming the
  perf category + budget. This avoids duplicate findings when both
  modules run.
- **`pagination`** — for each paginated GET (detected via
  `page` / `cursor` / `offset` / `limit` / `per_page` parameter or a
  `Link: rel="next"` header), walk pages up to
  `api.pagination_max_pages` and emit
  `PAGINATION-EMPTY-PAGE-ERROR` (4xx during the walk),
  `PAGINATION-CONTENT-TYPE-DRIFT` (content-type changed across
  pages), `PAGINATION-ENVELOPE-DRIFT` (JSON envelope changed across
  pages).
- **`error_shape`** — post-processes the issue catalogues emitted by
  the contract / negative / pagination checks and emits
  `ERROR-SHAPE-DRIFT` (medium) when the same endpoint surfaced more
  than one distinct error rule_id within a single run.
- **`backward_compat`** — diffs the current run's
  `<run-dir>/api/api-schema.json` snapshot against either the
  snapshot at `--diff-since <run-id>` or the alphabetically last
  sibling snapshot under `.sentinel/runs/`. Findings:
  `COMPAT-REMOVED-ENDPOINT` (high), `COMPAT-REMOVED-REQUIRED-RESPONSE-FIELD`,
  `COMPAT-ADDED-REQUIRED-REQUEST-FIELD`, `COMPAT-CHANGED-RESPONSE-TYPE`.

Persisted artifacts (CLAUDE §11):

```
<run-dir>/api/
  index.json                          # ApiRunOutcome (sum of all checks)
  contract.json                       # ApiCheckResult (when contract ran)
  negative.json
  auth.json
  pagination.json
  error_shape.json
  latency.json
  backward_compat.json
  api-schema.json                     # ApiSchemaSnapshot (for next run's diff)
```

**Safety boundary (CLAUDE §30):** aggressive fuzzing is forbidden.

- `api.negative_max_payload_kb` is clamped at the config-schema
  layer to `[1, 64]` KB; `api.negative_max_variants_per_endpoint`
  is clamped to `[1, 16]`.
- `modules.api.http_client.safe_request` enforces an absolute
  `ABSOLUTE_MAX_REQUEST_BYTES = 64 KB` cap regardless of config.
  Bodies above the cap raise `RequestTooLargeError` **before** the
  request is issued.
- The negative variant catalogue is a fixed, named list. The module
  does not call into any fuzz library.
- No CLI flag named `--aggressive`, `--fuzz`, `--brute`, `--stress`,
  `--unbounded`, or `--no-rate-limit` exists.
- The forbidden-literal guard
  `tests/security/test_api_no_aggressive_flags.py` greps
  `modules/api/` + the `sentinel api` CLI and fails CI on
  re-introduction.

### 10.4 Accessibility testing

Capabilities:

- Axe-core integration.
- Keyboard navigation.
- Focus order.
- Missing labels.
- ARIA misuse.
- Contrast checks.
- Modal traps.
- Form errors.
- Landmark structure.
- Screen-reader name detection.

#### 10.4.1 MVP delivery (Phase 11)

The accessibility module ships in Phase 11 as the second concrete `SentinelModule` (CLAUDE §9, ADR-0016). It is the first module that does **not** drive a Playwright spec set — accessibility checks are per-route, not per-test, so the module pairs the standard module lifecycle with a dedicated runner.

- **Module package:** `modules/accessibility/` houses `AccessibilityModule(SentinelModule)`. Importing the package auto-registers the module with the process-wide `ModuleRegistry` so `sentinel audit` and `sentinel a11y` both pick it up without bespoke wiring.
- **Lifecycle:** `validate_prerequisites → plan → execute → collect_evidence → emit_findings → emit_metrics → summarize`. `plan()` resolves the route set in priority order: CLI `--routes` → `discovery.json` → `config.accessibility.routes` → `("/",)` default. `execute()` calls the configured `A11yRunner` (production: `LocalA11yRunner`; tests: `StubA11yRunner`).
- **Runner abstraction (ADR-0016 §4):** `A11yRunner` is a `Protocol` over `run(invocation: A11yInvocation) -> A11yRunOutcome`. `LocalA11yRunner` spawns `sentinel-ts audit-a11y --input <run-config>.json` via `subprocess.run`, captures stderr, and reads the per-route JSON artifacts the TS subcommand writes under `<run-dir>/a11y/`.
- **TS subcommand:** `sentinel-ts audit-a11y` reads a deterministic JSON config (`run_id`, `target`, `out_dir`, `routes`, `axe_tags`, `request_timeout_ms`, `keyboard_max_tabs`), launches Chromium via `@playwright/test`, navigates each route, injects axe-core, runs the keyboard / landmark / accessible-name helpers (`packages/ts-runtime/src/a11y/*.ts`), writes one `<route-slug>.json` per route plus a top-level `index.json`, and exits 0 even when violations are found. Non-zero exits are reserved for runtime failures (Chromium launch, missing axe-core, etc.).
- **Check set (PRD §10.4 capabilities):** axe-core for rule-based violations including contrast; `walkFocus` for tab order + focus-visible + positive-tabindex detection; `detectFocusTrap` for modal escape; `detectLandmarkIssues` for required (`<main>`) + recommended (`<header>`, `<nav>`, `<footer>`) landmarks; `detectMissingAccessibleNames` for the ARIA name chain (`aria-labelledby` → `aria-label` → label text → visible text → `title`; **placeholders are not a sufficient fallback**).
- **Findings translation:** `modules.accessibility.findings.findings_from_pages` maps each `A11yPageResult` to PRD §18.2 `Finding` records. Severity mapping: axe `critical|serious → high`, `moderate → medium`, `minor → low`; keyboard `focus-trap → high`, `focus-visible|keyboard-navigation → medium`; landmark `missing → medium`, `duplicate → low`; accessible-name → `medium`. Confidence: `0.95` for stable axe rules, `0.6` for axe `experimental` rules, `0.9` for deterministic Python checks. Curated remediation strings live in `_AXE_REMEDIATIONS`; uncurated rules fall back to axe's `help` text.
- **Wire format:** the per-route JSON envelope carries `schema_version: "1"` (`A11Y_RESULT_SCHEMA_VERSION` constant on both runtimes). Future breaking changes bump the constant.
- **CLI:** `sentinel a11y` runs the canonical `RunLifecycle` restricted to the accessibility module. Options: `--url`, `--routes`, `--axe-tags`, `--discovery`. Exit codes: 0 (no high/critical findings), 1 (quality gate failed), 2 (config / CLI usage error), 4 (unsafe target), 5 (sentinel-ts binary missing), 6 (runner failure).
- **Safety + tone (CLAUDE §28):** every description begins with "Automated accessibility check found"; the phrases "fully WCAG compliant" / "WCAG compliant" never appear in product output. A forbidden-phrase guard (`tests/security/test_no_wcag_compliance_claims.py`) scans the module + TS helper packages on every CI run.
- **Dependency:** `axe-core` is **not** a workspace dependency. Projects that adopt the accessibility module install it themselves (`pnpm add axe-core`); the TS helper resolves it via `require.resolve('axe-core/axe.min.js')` at runtime and raises a typed `AxeCoreNotInstalledError` when missing.

### 10.5 Performance testing

Capabilities:

- Page-level budgets.
- Route-level budgets.
- API latency budgets.
- LCP/CLS/INP approximation.
- JS bundle budget.
- CPU blocking detection.
- Network waterfall analysis.
- Memory leak checks.
- Repeated navigation stability.

#### 10.5.1 MVP delivery (Phase 12, ADR-0017)

- **Module.** `modules.performance.PerformanceModule` inherits from `engine.modules.base.SentinelModule` and follows the seven-step lifecycle (CLAUDE §9). The module reuses the runner-Protocol pattern introduced in ADR-0016: `execute()` calls an injected `PerformanceRunner` (production: `LocalPerformanceRunner`) instead of the Phase-08 Playwright spec runner, so each check runs against a route rather than a spec.
- **Deterministic evaluators.** Each PRD §10.5 capability is owned by a pure Python evaluator: `page_budget.evaluate_page_budgets` for LCP/TTFB/INP/CLS medians, `api_latency.evaluate_api_latency` for per-endpoint P50/P95, `bundle_cpu.evaluate_bundle_size` + `bundle_cpu.evaluate_long_tasks` for transferred-bytes and main-thread blocking, and `nav_stability.evaluate_nav_stability` for first-to-last percentage growth on JS heap + DOM-node count. The Python side is the single source of truth for severity policy; the TS runtime never grades.
- **Severity policy.** Page-budget, bundle-size, and CPU-blocking exceedances are `high` when overage exceeds 50 %, otherwise `medium`. API-latency P95 violations are `medium` by default and escalate to `high` when overage exceeds 100 %. Nav-stability findings are always `low` with confidence `0.5` — they are heuristics (CLAUDE §27); Phase 14 should not over-block on this signal.
- **TS runtime.** `sentinel-ts audit-perf --input <run-config>.json` (new subcommand) launches a Chromium tab via `@playwright/test`, installs PerformanceObservers before navigation (LCP / CLS / INP / longtask), captures TTFB + DCL + load from `PerformanceNavigationTiming`, observes every JS bundle + API response via the Playwright `response` event, runs the per-route sample loop (`samples`, default 3) and the repeated-nav loop (`repeated_nav_samples`, default 5), and writes one `<route-slug>.json` per route under `<run-dir>/perf/` plus a top-level `index.json`. The launcher is injectable so vitest exercises the full dispatch path without Chromium.
- **Wire format.** The per-route envelope carries `schema_version: "1"` (`PERF_RESULT_SCHEMA_VERSION` constant on both runtimes). Future breaking changes bump the constant. ADR-0017 §5 owns the rationale.
- **CLI.** `sentinel perf` runs the canonical `RunLifecycle` restricted to the performance module. Options: `--url`, `--routes`, `--samples`, `--repeated-nav-samples`, `--discovery`. Exit codes: 0 (no high/critical findings), 1 (quality gate failed), 2 (config / CLI usage error), 4 (unsafe target), 5 (sentinel-ts binary missing), 6 (runner failure). Every text-mode line ends with `measurement_kind: synthetic (lab; not Real-User Monitoring)`; JSON mode emits `"measurement_kind": "synthetic"`.
- **Safety + tone (CLAUDE §27).** Every Finding description begins with "Synthetic performance check"; descriptions also include the literal phrase "lab measurements" or "synthetic" so readers cannot mistake the output for RUM data. A forbidden-phrase guard (`tests/security/test_synthetic_perf_labeling.py`) scans the module + TS helper packages on every CI run for stronger RUM claims.
- **Dependency.** No new workspace dependency. The TS subcommand reuses the existing `@playwright/test` dynamic import resolved by the launcher; nothing has to be installed in projects that do not run `sentinel perf`.

### 10.6 Visual testing

Capabilities:

- Baseline snapshots.
- Responsive breakpoints.
- Component screenshots.
- Full-page screenshots.
- Theme comparison.
- Diff thresholding.
- Ignore regions.
- Dynamic content masking.

#### 10.6.1 Phase 21 — MVP delivery

Phase 21 (ADR-0026) ships the diff + acceptance pipeline as the
release-ready slice of §10.6. Concrete behaviour:

- **Module.** `modules/visual.VisualModule` follows the standard
  SentinelQA module lifecycle (`validate_prerequisites` → `plan` →
  `execute` → `emit_findings` → `emit_metrics` → `summarize`). It
  consumes PNGs already on disk; the Playwright TS capture step is
  a follow-up wire and is *not* a Phase 21 deliverable.
- **Diff math.** Pure-Python via Pillow. `pixel_diff` returns a
  differing-pixel count plus a red-highlighted overlay PNG. `ssim`
  (single-scale Wang et al., luminance channel, no Gaussian window
  so the value is platform-stable) is the optional perceptual
  filter; when enabled, findings fire only when BOTH the pixel
  threshold AND the SSIM threshold cross.
- **Storage layout.** Baselines live at
  `.sentinel/baselines/<viewport>/<route-slug>.png` with an
  `index.json` carrying sha256, captured-at, captured-by-run-id,
  and the applied masks per row. Run artifacts land under
  `<run-dir>/visual/`: `current/` for captures, `diff/` for
  overlays, `index.json` for the per-pair status summary.
- **Masking.** `visual.masks` accepts either a `selector` (the TS
  capture helper hides the element before screenshot — contract
  documented, capture-side wire ships with the future capture
  task) or a static `rect` (the Python diff layer paints both
  images grey before comparison). Wildcard route `*` matches every
  route; prefix glob `admin*` matches every route that begins with
  `admin`.
- **Viewports.** Defaults: `mobile (375×812)`, `tablet (768×1024)`,
  `desktop (1280×800)`. Viewport names must match `^[a-z0-9_-]+$`
  and are unique per configuration.
- **CLI.** `sentinel visual` exposes three subcommands:
  `diff` (default — runs the lifecycle restricted to the visual
  module), `accept` (promotes captures into the baseline tree —
  refused under CI), and `capture` (stages an external PNG tree
  as the run's `current/`).
- **CI-acceptance guard.** `sentinel visual accept` refuses to
  promote whenever the CLI is in CI mode (`--ci` flag OR `CI` /
  `SENTINEL_CI` truthy in the env), exiting with code `4`
  (unsafe target). Every refusal writes a
  `visual.accept.refused_ci` audit-log entry under the supplied
  current root so operators have a paper trail.
- **Findings.** Three categories ship: `visual_pixel_diff`
  (medium), `visual_size_mismatch` (high — different pixel
  dimensions are almost never a noise event), and
  `visual_missing_current` (medium — baseline present, capture
  missing). `missing_baseline` is the operator's signal to run
  `sentinel visual accept` and does NOT emit a finding.
- **Exit codes.** `0` no findings, `1` quality gate failed
  (findings present), `2` invalid config / CLI usage, `4` safety
  policy blocked OR CI-mode accept refused, `6` module failed,
  `7` internal error.

### 10.7 Security testing

Safe checks:

- Security headers.
- Cookie flags.
- CORS configuration.
- CSRF token presence.
- Reflected XSS safe probes.
- Stored XSS safe probes in sandbox only.
- SQL injection safe probes in sandbox/local only.
- Auth boundary testing.
- IDOR smoke checks.
- Sensitive data in DOM/network.
- Secrets in frontend bundles.
- Dependency scan integration.
- Static security scan integration.
- SARIF export.

#### 10.7.1 MVP delivery (Phase 13)

Phase 13 ships `modules.security.SecurityModule(SentinelModule)` and the
`sentinel security` CLI command. ADR-0018 owns the rationale; this
section names what is actually shipped and the safety contract:

- **Module shape.** `SecurityModule` inherits from
  `engine.modules.base.SentinelModule` and runs the seven-step
  lifecycle (CLAUDE §9). `execute()` drives every enabled check via a
  shared `CheckContext` (immutable, carries the `httpx.Client`,
  `Target`, `SafetyDecision`, audit-log path, env snapshot, and route
  list). Findings are translated by
  `modules.security.findings.findings_from_checks` and persisted
  alongside per-check artifacts under `<run-dir>/security/`.
- **Per-check files.** Each PRD §10.7 bullet has its own module under
  `modules/security/checks/`:

  - `headers.py` — OWASP-aligned rule set (HSTS / CSP / XFO /
    XCONTENT-TYPE-OPTIONS / Referrer-Policy / Permissions-Policy).
  - `cookies.py` — `HttpOnly` / `Secure` / `SameSite` evaluation,
    auth-cookie heuristic, dedicated rule for `SameSite=None`
    without `Secure`.
  - `cors.py` — OPTIONS preflight from the synthetic origin
    `https://sentinelqa.invalid`; flags wildcard+credentials and
    reflective ACAO.
  - `csrf.py` — form parser + token / meta / `SameSite` heuristic;
    POST/PUT/PATCH/DELETE forms only.
  - `xss_reflected.py` — non-executable marker (`__SENTINELQA_XSS__`)
    reflected unescaped → high finding; confidence reduced when a
    `script-src 'self'` CSP is present.
  - `xss_stored.py` — gated. Refuses to run unless
    `security.mode == "authorized_destructive"`,
    `security.checks.xss_stored == true`, AND a valid proof-of-
    authorization document is configured. Returns
    `skipped=True`+reason otherwise (CLAUDE §37: no fake completion).
  - `sqli.py` — boolean + capped time-based behavioural probe; runs
    only against local hosts (loopback / RFC1918) OR
    `authorized_destructive` + proof. Compares status, body length,
    and elapsed time across baseline / true / false probes.
  - `idor.py` — second-user resource access. Skipped (with `info`
    reason) when `auth.second_user.token_env` is absent. Uses a
    bearer token only — username/password login orchestration is a
    Phase 17 follow-up.
  - `frontend_secrets.py` — JS bundle scan via the detection-mode
    regex catalog in `modules/security/secret_patterns.py`. DOM /
    localStorage / sessionStorage scanning is opt-in via JSON
    snapshots under `<run-dir>/security/snapshots/<route-slug>.json`
    (the Playwright capture helper that produces these is documented
    separately).
  - `deps.py` — `pip-audit` (default-on if `requirements.txt` /
    `poetry.lock` / `uv.lock` is present), `npm audit` (default-on if
    `package-lock.json` / `npm-shrinkwrap.json` is present),
    `osv-scanner` (opt-in). Adapters never auto-install — the doctor
    command surfaces missing tools.
  - `sast.py` — `semgrep --config auto --json`. Opt-in via both
    `security.checks.sast=true` and
    `security.dependency_scanners.semgrep=true`.
- **Rule catalog + SARIF.** `modules/security/rules.py` is the single
  source of truth for stable `SEC-*` rule IDs (e.g.
  `SEC-HEADERS-HSTS-MISSING`). On import, the package registers every
  rule with `engine.reporter.sarif_rules.default_sarif_registry()`;
  the Phase-03 SARIF writer reads them by category. Rule IDs are
  stable across releases — renaming one is a breaking change for any
  downstream dashboard.
- **Wire format.** `security/index.json` + `security/<check>.json`
  versioned by `SECURITY_RESULT_SCHEMA_VERSION="1"` (Pydantic models
  in `modules/security/models.py`). Finding records (PRD §18.2)
  carry the per-check artifact path as evidence.
- **Safety contract.** Every public `run_*` function in
  `modules/security/checks/` begins with `SafetyPolicy().enforce(...)`
  OR with an explicit precondition gate (e.g. `_allowed_to_run`,
  `_second_user_token`) that returns `skipped=True` BEFORE any I/O.
  The AST guard in `tests/security/test_module_calls_policy.py`
  enforces this on every CI run. The forbidden-flag guard in
  `tests/security/test_security_forbidden_flags.py` enforces
  CLAUDE §6 on the new CLI surface (no `--stealth`, no `--evade`,
  no `--bypass-*`, etc.).
- **Audit logging.** Every probe writes one redacted entry to
  `.sentinel/runs/<run-id>/audit.log` via
  `engine.policy.audit_log.write_audit_entry`. Stored XSS, SQLi,
  and IDOR additionally log `skipped` events with the precise reason
  when they refuse to run.
- **CLI.** `sentinel security` replaces the Phase-02 stub. Options:
  `--url` (override `target.base_url`), `--routes` (comma-separated
  override), `--discovery` (pull routes from a `discovery.json`),
  `--mode safe|authorized_destructive`,
  `--proof-of-authorization <path>`, `--checks <list>` (restrict the
  set, intersected with config). Exit codes follow the canonical
  grid (0/1/2/4/5/6 per CLAUDE §13).
- **Config surface.** `security.checks.{headers, cookies, cors, csrf,
  xss_reflected, xss_stored, sqli, idor, frontend_secrets,
  dependency_scan, sast}` per-check toggles;
  `security.dependency_scanners.{pip_audit, npm_audit, osv_scanner,
  semgrep}` adapter toggles; `security.routes` for the default route
  list; `security.request_timeout_seconds`;
  `security.max_requests_per_second` for the token-bucket limiter;
  `auth.second_user.{username_env, password_env, token_env,
  user_id}` for IDOR.

#### 10.7.2 Extended Security Skill Catalog (Phase 32, ADR-0044)

Phase 32 extends the Phase-13 catalog with eight defensive-only
assessment checks drawn from the Anthropic Cybersecurity Skills
taxonomy plus our existing follow-up backlog. Every check stays
inside the CLAUDE.md §6 safety boundary — no offensive payloads, no
exploit material, no WAF / detection bypass, no aggressive fuzzing.
Each check maps every finding to a canonical taxonomy id (`cwe_id`,
`attack_id`, and where applicable `owasp_api_id`) so SARIF / dashboard
consumers can deep-link to standards instead of internal jargon.

- **Schema v2 (Task 32.09).** `FINDINGS_SCHEMA_VERSION` bumps from
  `"1"` to `"2"`. The `Finding` model gains three optional
  taxonomy fields. v1 wire documents parse cleanly into the v2 model
  (the new fields default to `null`); the canonical re-stamp helper
  lives at
  `engine.domain.migrations.findings_1_to_2.migrate`. The SARIF
  writer emits `runs[].taxonomies` referencing `cwe.mitre.org`,
  `attack.mitre.org`, and the OWASP API Top-10 editions index when
  any finding carries the matching id.
- **`modules/security/checks/jwt_weakness.py` (Task 32.01).** Walks
  every JWT-shaped string observed in `Authorization` headers and
  cookies; flags `alg=none` (CWE-347, T1606.001), HS256 verifying
  against a fixed 6-entry weak-secret wordlist (CWE-347), missing
  `exp` (CWE-613), expired `exp` (CWE-613), and missing `iss`/`aud`
  for multi-tenant tokens (CWE-345). The wordlist is hard-coded; the
  scanner does NOT iterate against any external dictionary.
- **`modules/security/checks/cookies.py` extended (Task 32.02).**
  Adds rules for missing `__Host-` / `__Secure-` prefix on
  session-shaped cookies (CWE-1004), over-broad `Domain` attribute
  (CWE-1275), and over-broad `Path=/` on sensitive cookies
  (CWE-1275). The `__Host-` carve-out for `Path=/` is honored.
- **`modules/security/checks/tls_posture.py` (Task 32.03).**
  Read-only TLS handshake against the allowlisted host. Records
  protocol version, cipher suite, leaf cert SHA-256 / issuer / SANs /
  expiry, and HSTS status. Flags legacy TLS versions (CWE-326,
  T1573), weak ciphers (CWE-326, T1573), expired / soon-to-expire
  certs (CWE-295), and missing or short HSTS (CWE-319). The probe
  is strictly read-only: no downgrade attempts, no cipher
  brute-forcing.
- **`modules/security/checks/graphql_safety.py` (Task 32.04).**
  Fixed 3-query probe set (introspection, depth-5, alias bomb) plus
  optional anonymous mutation probes (one request per discovered
  mutation). Flags `graphql-introspection-enabled` (CWE-200),
  `graphql-no-depth-limit` / `graphql-no-complexity-limit`
  (CWE-770), and `graphql-mutation-no-auth` (CWE-862 /
  OWASP API-2023-05).
- **`modules/security/checks/api_bola_bfla.py` (Task 32.05).**
  Replays observed identity-A API calls under identity B. Hard-gated
  behind `security.mode == "authorized_destructive"` AND a non-empty
  `target.proof_of_authorization`; capped at 50 endpoints per run.
  Surfaces BOLA findings (CWE-639 / OWASP API-2023-01) and BFLA
  findings (CWE-863 / OWASP API-2023-03).
- **`modules/security/checks/frontend_only_auth_deeper.py` (Task
  32.06).** Augments the Phase-19 frontend-only-auth detector with a
  deeper probe: re-issues every observed XHR / fetch URL
  anonymously and flags 200-with-body responses (CWE-862 /
  OWASP API-2023-01). Apparent-public endpoints
  (`/api/public/...`, `/api/health`) are excluded.
- **`modules/security/checks/bundle_secrets.py` (Task 32.07).** Fetches
  every JS bundle the page loaded (streamed; 50 MiB cap with a
  `truncated` flag), scans for AWS / GCP / Azure / Stripe / GitHub /
  Slack tokens and PEM private keys (all CWE-540). Match prefixes are
  redacted to 8 characters; raw match text never enters the audit log.
- **`modules/security/checks/ssrf_redirect.py` (Task 32.08).** For
  every URL-shaped form field / query parameter, sends a fixed 6-entry
  SSRF payload list (loopback, AWS / GCP metadata, file://, redis
  gopher) and a fixed 2-entry open-redirect bait list. Flags
  `ssrf-suspected` (CWE-918 / OWASP API-2023-07) and `open-redirect`
  (CWE-601). Same destructive-mode + proof-of-authorization gate as
  Task 32.05.
- **Safety guard.** `tests/security/test_no_offensive_checks.py`
  greps the new modules for forbidden tokens (`exploit`, `bypass`,
  `shellcode`, `obfuscate`, `evade`, `captcha_bypass`, `stealth`,
  etc.) and asserts per-module load-bearing invariants: the JWT
  module never loads an external wordlist; the SSRF / GraphQL
  payload sets are module-level `Final[tuple[str, ...]]`; the TLS
  module never writes application-layer bytes to its socket outside
  the SSL handshake.

### 10.8 Chaos/adversarial testing

Safe chaos tests:

- Slow network.
- Offline mode.
- API 500 mocking.
- API timeout mocking.
- Expired session.
- Invalid token.
- Missing permissions.
- Duplicate submission.
- Double-click race.
- Back/forward navigation.
- Refresh mid-flow.
- Large payload.
- Empty dataset.
- Browser storage corruption.

#### 10.8.1 MVP delivery (Phase 23)

Phase 23 ships the chaos module as a Python `ChaosModule(SentinelModule)`
backed by a TypeScript chaos helper surface (ADR-0028). The bridge is the
same JSONL pattern Phase 11 (a11y) and Phase 12 (perf) already use:

- **Scenario catalog (13 entries, all four PRD §10.8 categories).**
  `modules.chaos.scenarios.CATALOG` is the canonical source of truth
  for both runtimes — `network.{slow_3g, offline, api_500, api_timeout}`,
  `session.{expired_token, missing_permissions}`, `ux.{duplicate_submit,
  double_click_race, back_forward, refresh_mid_flow}`,
  `data.{empty_dataset, large_dataset, storage_corruption}`.
- **TS chaos helpers** live in `@sentinelqa/ts-runtime/chaos`:
  `chaosNetwork(page, scenario)`, `chaosSession(page, scenario)`,
  `chaosDuplicateSubmit(locator)` /
  `chaosDoubleClickRace(locator)` /
  `chaosBackForward(page)` /
  `chaosRefreshMidFlow(page)`, plus
  `chaosEmptyDataset(page, …)` /
  `chaosLargeDataset(page, …)` /
  `chaosCorruptStorage(storage, keys)`. Every helper installs
  `page.route()` handlers; none re-signs production JWTs, rotates
  proxies, or attempts detection bypass.
- **Wire format.** TS helpers append `ChaosEvent` records (one JSON
  object per line) to `<run-dir>/chaos/events.jsonl`. Each event names
  the `scenario_id`, `category`, `flow`, `observation` (one of ten
  enums including the positive `handled_gracefully`), and optional
  `route` / `detail` / `evidence` (flat `str -> str` map). The Python
  ingestion layer (`modules.chaos.ingestion`) parses each line through
  Pydantic with `extra="forbid"`, caps the file at 8 MiB, and groups
  events into `ChaosScenarioResult` records.
- **Bounded knobs (CLAUDE.md §6).** The `chaos:` config block clamps:
  `slow_3g_kbps ∈ [100, 10_000]`, `slow_3g_rtt_ms ∈ [50, 5_000]`,
  `api_timeout_abort_ms ∈ [1_000, 120_000]`,
  `large_dataset_items ∈ [100, 10_000]`. Below-floor values for
  `slow_3g_kbps` would turn the scenario into a denial-of-service
  amplifier; above-ceiling values for `api_timeout_abort_ms` would
  let the helper hang the runner indefinitely.
- **Default OFF (CLAUDE.md §6).** `modules.chaos` defaults `false`.
  The PRD §21.3 CI `nightly` preset flips it on; `fast` / `standard`
  / `full` / `release` do not. Operators may also run the module ad
  hoc via `sentinel chaos`, which always honors the standard
  `SafetyPolicy` (no destructive scenarios escape `safe` mode).
- **Artifacts.** `<run-dir>/chaos/<category>.json` per category +
  `<run-dir>/chaos/index.json` aggregate, both stamped with
  `CHAOS_RESULT_SCHEMA_VERSION = "1"`. The raw `events.jsonl` remains
  the canonical event log; chaos artifacts never re-copy it.
- **Findings.** Each "bad" observation maps to one of nine rule IDs
  (`chaos-uncaught-error`, `chaos-no-error-state`,
  `chaos-session-expired-no-redirect`, `chaos-permission-missing-bad-ux`,
  `chaos-duplicate-submit-accepted`, `chaos-lost-form-state`,
  `chaos-white-screen-on-refresh`, `chaos-missing-empty-state`,
  `chaos-dom-explosion`, `chaos-crash-on-corrupted-storage`).
  Severities mirror UX impact: a missing empty state is high, a lost
  form value is medium. `handled_gracefully` never raises a finding.
- **CLI.** `sentinel chaos` replaces the Phase 02 stub. Flags:
  `--url`, `--scenarios <csv of scenario_ids>`, `--categories <csv>`,
  `--flows <csv>`, `--events <path>` (defaults to
  `<run-dir>/chaos/events.jsonl`). Exit codes follow PRD §13.2:
  0 (no high/critical), 1 (high/critical or incomplete), 2 (config),
  4 (unsafe target), 6 (runner failure).
- **Safety guard.** `tests/security/test_chaos_no_evasion_flags.py`
  greps the chaos package + CLI source for compound forbidden
  literals (`stealth_mode`, `bot_detection_bypass`, `proxy_rotation`,
  `captcha_bypass`, …) and introspects the Typer parameters to
  refuse any `--aggressive` / `--bypass` / `--stealth` /
  `--undetectable` / `--unbounded` / `--no-rate-limit` /
  `--ignore-robots` / `--evade*` flag.

### 10.9 LLM-code-specific audits

This is SentinelQA’s strongest differentiator.

Checks:

- Buttons with no handlers.
- Forms that do not submit.
- UI-only auth gates.
- Mock data shipped to production build.
- Fake API endpoints referenced but missing.
- Generated links to nonexistent routes.
- Component state not persisted.
- Missing error/loading states.
- Inconsistent frontend/backend validation.
- CRUD create works but edit/delete missing.
- Role UI present but backend permissions missing.
- Payment UI without sandbox integration.
- “Coming soon” placeholders hidden in flows.
- Console errors ignored by generated UI.
- Hardcoded demo credentials.
- Insecure localStorage secrets.

#### 10.9.1 MVP delivery (Phase 19, ADR-0024)

`modules.llm_audit.LlmAuditModule` is the fifth concrete
`SentinelModule` (CLAUDE §9, ADR-0015) and the first that ships
without its own runner Protocol — every check runs as a pure Python
function over already-captured signals. The module loads its inputs
from disk via `modules.llm_audit.inputs.load_inputs`:
`discovery.json` / `api.json` / `forms.json` next to the discovery
artifact root, plus optional `signals.json` and `source_files.json`
under `--signals <root>`. Malformed JSON or unexpected shapes are
dropped silently, so the audit never crashes on user input.

Sixteen stable rule IDs are owned by `modules.llm_audit.rules`:

- `LLM-DEAD-BTN` (high, 0.8) — interactive button observed no static
  handler and no runtime effect within 2 s.
- `LLM-FAKE-ROUTE` (high, 0.85) — internal link resolves to a 4xx
  route or to a route never reached by discovery.
- `LLM-FAKE-ENDPOINT` (high, 0.75) — frontend references an endpoint
  neither observed nor declared in OpenAPI / GraphQL.
- `LLM-MOCK-DATA-SHIPPED` (high, 0.85) — bundle / rendered text
  contains `mockData`, `__MOCK__`, faker patterns, "John Doe",
  `*@example.com`, or hardcoded mock imports.
- `LLM-FORM-NO-SUBMIT` (high, 0.9) — form lacks `action`/`onsubmit`,
  or planner exercised it and saw no network request.
- `LLM-INCOMPLETE-CRUD` (medium, 0.7) — resource exposes create
  affordance but read / update / delete missing; UI-only-create bumps
  to `high`.
- `LLM-UI-ONLY-AUTH` (critical, 0.9) — UI hides a route the backend
  serves 2xx to a low-priv user.
- `LLM-HARDCODED-CRED` (high, 0.85) — source file embeds a literal
  JWT / OpenAI / Stripe / AWS / db-connection / demo-admin
  credential. The matched span is replaced with
  `[REDACTED:hardcoded_credential]` before the snippet is double-
  redacted through `engine.policy.redaction.redact` (CLAUDE.md §33).
- `LLM-CLIENT-SECRET-STORAGE` (medium, 0.75) — browser-storage entry
  matches the redactor's secret detection, looks like a JWT, or has
  a token-shaped key name.
- `LLM-NO-LOADING-STATE` (medium, 0.7) — runner delayed a target API
  call and observed no loading indicator.
- `LLM-NO-ERROR-STATE` (high, 0.85) — runner forced a 5xx and the UI
  showed no error state; `ui_reported_success` bumps severity.
- `LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS` (high, 0.9) — frontend
  refused a malformed payload the backend accepted (server-side
  validation gap).
- `LLM-VALIDATION-MISMATCH-FRONTEND-MISSING` (medium, 0.85) —
  backend rejects a payload the frontend would submit as-is.
- `LLM-PLACEHOLDER-TEXT` (low, 0.95) — placeholder text leaked into a
  user-facing flow; bumps to `medium` on authenticated / P1 flows
  and `high` on P0 flows.
- `LLM-CONSOLE-ERROR-IGNORED` (medium, 0.8) — console error captured
  while the UI reported success on the same route.
- `LLM-UNHANDLED-PROMISE` (medium, 0.85) — unhandled promise
  rejection observed. Third-party hosts are filtered via
  `--third-party-hosts <suffix-list>`.

The module persists `<run-dir>/llm_audit/index.json` summarising
which checks ran, which had signals, and how many findings each
produced. Status policy: `skipped` when no check had any signal,
`failed` when any high/critical finding fires, otherwise `passed`.

CLI: `sentinel llm-audit` replaces the Phase-02 stub with options
`--url / --discovery / --signals / --checks / --third-party-hosts`
and the canonical exit-code grid (0 success or skipped, 1 quality
gate failed, 2 invalid CLI / config, 4 unsafe target, 6 module
error). The lifecycle, safety policy, reporter dispatch, and audit
log are unchanged.

Report differentiator: `engine.reporter.html_writer` adds an
`llm_audit` context block, and the HTML template renders a dedicated
"LLM-Code Audit" section listing every fired rule with severity and
count. `engine.reporter.pr_comment._render_llm_audit_section` emits
the matching Markdown table. Both renderers stay silent on runs
without `llm_audit` activity so non-LLM workflows don't see an empty
differentiator block.

Test surface: 13 per-check integration tests, a broken-fixture sweep
under `tests/fixtures/llm_audit_broken/` that exercises ≥ 11 of the
13 checks end-to-end, CLI integration tests covering every exit-code
branch, and reporter integration tests asserting the HTML + PR
sections render only when the module ran. Coverage on
`modules/llm_audit/` is ≥ 94 % per file (floor 90 %).

---

## 11. System Architecture

### 11.1 High-level architecture

```text
┌──────────────────────────────────────────────────────┐
│ Interfaces                                            │
│ CLI | Python SDK | TypeScript API | MCP Server | CI   │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│ Agent Orchestrator                                    │
│ Planner | Executor | Analyzer | Healer | Reporter     │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│ Capability Modules                                    │
│ Functional | API | A11y | Perf | Visual | Security    │
│ Chaos | LLM-code Audit | Coverage | Policy            │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│ Runtimes                                              │
│ Playwright TS | Python wrapper | Scanner adapters     │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│ Target App / Browser / API / Source Code / CI         │
└──────────────────────────────────────────────────────┘
```

### 11.2 Repository structure

```text
sentinelqa/
  apps/
    cli/
    docs/
    dashboard/
  packages/
    python-sdk/
    ts-runtime/
    mcp-server/
    shared-schema/
  engine/
    orchestrator/
    discovery/
    planner/
    generator/
    runner/
    analyzer/
    healer/
    reporter/
    policy/
  modules/
    functional/
    api/
    accessibility/
    performance/
    visual/
    security/
    chaos/
    llm_audit/
  integrations/
    github/
    gitlab/
    browserstack/
    saucelabs/
    slack/
    jira/
    linear/
  examples/
    nextjs/
    fastapi/
    django/
    flask/
    react-vite/
    llm-broken/
    end-to-end-demo/
    mcp-claude-desktop/
    plugins/
  tests/
    unit/
    integration/
    e2e/
```

### 11.2.1 Example apps (Phase 26 delivery)

The Phase 26 example apps are runnable reference implementations under
`examples/`, each with its own `sentinel.config.yaml` and a top-level
Make target. The MVP set is:

| Directory | Stack | Loopback port | Make target | Config gate |
| --- | --- | --- | --- | --- |
| `examples/nextjs/` | Next.js 14 App Router, cookie session, in-memory CRUD, `/admin` role gate | `3000` | `make demo-nextjs` | `policy.min_quality_score: 85` |
| `examples/fastapi/` | FastAPI + Pydantic, Bearer auth, OpenAPI 3 dump | `8000` | `make demo-fastapi` | `policy.min_quality_score: 85` |
| `examples/django/` | Django 5, session auth, admin enabled, SQLite | `8001` | `make demo-django` | `policy.min_quality_score: 85` |
| `examples/flask/` | Flask 3, session auth, in-memory `Project` CRUD | `5001` | `make demo-flask` | `policy.min_quality_score: 85` |
| `examples/react-vite/` | Vite + React 18 SPA against `examples/fastapi/` | `5173` | `make demo-react-vite` | `discovery.engine: playwright`, `policy.min_quality_score: 85` |
| `examples/llm-broken/` | Intentionally broken Next.js — exhibits ≥ 8 PRD §10.9 anti-patterns | `3030` | `make demo-llm-broken` | `policy.min_quality_score: 0` (demo purpose is to surface findings) |
| `examples/end-to-end-demo/` | `docker compose` stack tying `nextjs/` + `fastapi/` together; `make demo` boots compose + runs `sentinel audit --ci`. Tear down with `make demo-down`. | `3000` (UI) / `8000` (API) | `make demo`, `make demo-down` | inherits `examples/nextjs/sentinel.config.yaml` |

Safety contract (CLAUDE.md §6 / PRD §2): every example binds to
`127.0.0.1` only — never to a public interface — and every credential
in the demo apps is public, documented in the matching `README.md`, and
local-only. The `examples/` tree is excluded from the monorepo's ruff,
mypy, Prettier, and coverage scopes; each example is typed and linted
by its own framework toolchain.

The phase Make target naming differs slightly from the plan's shorthand:
plan documents read `make demo:<name>` (with a colon) but GNU and BSD
`make` both treat `:` as the rule separator, so the literal targets use
`-` (`make demo-flask`, `make demo-nextjs`, …). The end-to-end stack
keeps the bare `make demo` / `make demo-down` form. The Phase 26
deliverable is the same set of demos in either notation.

### 11.3 Language strategy

- **TypeScript:** Playwright runtime and generated tests.
- **Python:** CLI/SDK orchestration, agent integration, reports, plugin system.
- **JSON Schema:** Shared machine-readable contracts.
- **YAML:** User configuration.

Rationale: Playwright is strongest in TypeScript, but Python is the best ecosystem for AI agents, orchestration, security scanning integration, and data/report processing.

---

## 12. Core Workflows

### 12.1 First-time setup

```bash
pip install sentinelqa
sentinel init
sentinel doctor
```

Expected output:

- Detect framework.
- Detect package manager.
- Detect Playwright installation.
- Create config.
- Create tests directory.
- Create CI template.

### 12.2 Local app audit

```bash
sentinel audit --url http://localhost:3000
```

Pipeline:

1. Load config.
2. Validate target is allowed.
3. Start discovery.
4. Generate or update test plan.
5. Execute selected modules.
6. Analyze failures.
7. Score result.
8. Generate report.
9. Return exit code.

### 12.3 PR diff audit

```bash
sentinel audit --diff origin/main...HEAD --url $PREVIEW_URL
```

Pipeline:

1. Parse changed files.
2. Map changed files to routes/components/APIs.
3. Select impacted tests.
4. Generate missing tests.
5. Run focused suite.
6. Run mandatory smoke suite.
7. Comment result on PR.

### 12.4 Test generation workflow

```bash
sentinel generate --url http://localhost:3000 --out tests/sentinel
```

Pipeline:

1. Discover app.
2. Build route and interaction graph.
3. Build test plan.
4. Generate tests.
5. Run generated tests.
6. Repair unstable locators.
7. Save tests and plan.

### 12.5 Failure repair workflow

```bash
sentinel fix --tests
```

Pipeline:

1. Read latest report.
2. Categorize failures.
3. For test bugs, propose patch.
4. Apply patch if safe or with approval.
5. Re-run affected tests.
6. Update report.

### 12.6 Safe security audit workflow

```bash
sentinel security --url http://localhost:3000 --mode safe
```

Pipeline:

1. Validate target allowlist.
2. Confirm non-production or explicit production-safe mode.
3. Run non-destructive checks.
4. Export SARIF.
5. Fail CI if policy threshold exceeded.

### 12.7 LLM agent workflow

```text
LLM coding agent writes code
        ↓
LLM calls SentinelQA discover
        ↓
SentinelQA returns risk map
        ↓
LLM calls SentinelQA audit
        ↓
SentinelQA returns structured failures
        ↓
LLM proposes code fix
        ↓
SentinelQA verifies fix
        ↓
PR marked ready or blocked
```

---

## 13. CLI Specification

### 13.1 Commands

```bash
sentinel init
sentinel doctor
sentinel discover
sentinel plan
sentinel generate
sentinel test
sentinel audit
sentinel functional
sentinel api
sentinel a11y
sentinel perf
sentinel visual
sentinel security
sentinel chaos
sentinel llm-audit
sentinel fix
sentinel report
sentinel ci
sentinel mcp
```

### 13.2 Exit codes

Deterministic and aligned with `CLAUDE.md` §13 (authority order `CLAUDE.md` §2 puts CLAUDE rules above the PRD, so the engineering constitution's exit-code grid is canonical). Every CLI command MUST exit with exactly one of these codes; the mapping is owned by `engine/errors/codes.py` and `engine/policy/exit_codes.py` (Phase 01).

| Code | Meaning | Raised by (Phase 01 exception) |
|---:|---|---|
| 0 | Success | — |
| 1 | Quality gate failed | `QualityGateFailedError` |
| 2 | Configuration error | `ConfigError` and subclasses |
| 3 | Runtime error (uncategorized non-fatal failure) | `SentinelError` raised without a more specific subclass |
| 4 | Unsafe target blocked | `UnsafeTargetError` and subclasses |
| 5 | Dependency missing | `DependencyMissingError`, `PluginError` (load-time) |
| 6 | Test execution failed | `TestExecutionError` |
| 7 | Internal error | `InternalError`, `PluginError` (runtime crash) |

The earlier draft of this section listed "Target not authorized = 3" and "Unsafe command rejected = 6"; that ordering was retired during Phase 01 conflict resolution to align with `CLAUDE.md` §13 and the Phase 01 task spec `plans/phase-01-core-domain-config/04-exceptions.md`. The Phase 01 gate review checks that an unallowlisted host produces exit code 4, not 3 or 6.

### 13.3 Example commands

```bash
sentinel audit --url http://localhost:3000 --modules functional,a11y,perf
sentinel security --url http://localhost:3000 --safe
sentinel generate --source . --url http://localhost:3000
sentinel fix --latest --apply safe
sentinel report --format html,json,sarif
sentinel ci --preview-url $PREVIEW_URL --diff origin/main...HEAD
```

---

## 14. Python SDK Specification

### 14.1 Basic usage

```python
from sentinelqa import Sentinel

qa = Sentinel(project_path=".")

result = qa.audit(
    url="http://localhost:3000",
    modules=["functional", "accessibility", "performance", "security"],
    safe_mode=True,
)

print(result.quality_score)
print(result.release_decision)
```

### 14.2 Agent-friendly usage

```python
from sentinelqa import Sentinel

qa = Sentinel(project_path=".", machine_readable=True)

plan = qa.plan(url="http://localhost:3000")
result = qa.run_plan(plan)

if not result.passed:
    for failure in result.failures:
        print(failure.to_agent_message())
```

### 14.3 SDK classes

```python
Sentinel
AuditResult
Finding
Evidence
TestPlan
Flow
RiskMap
QualityGate
Policy
ModuleResult
RepairSuggestion
```

### 14.4 SDK requirements

- Typed Python API.
- Pydantic models.
- Async support.
- JSON serialization.
- Stable schema versions.
- Error classes for agent handling.

### 14.5 MVP delivery (Phase 16)

The Phase-16 SDK ships:

- **`Sentinel` facade** (`packages/python-sdk/src/sentinelqa/_facade.py`):
  constructor takes `project_path=".", *, config=None, machine_readable=False, artifacts_root=None`. Class method `Sentinel.from_config(path)` pins to an explicit config path. Methods (sync): `discover(url)`, `plan(url|graph=…, risk_map=…)`, `generate_tests(plan, out_dir, *, discovery=…, base_url="", force=False)`, `audit(url, *, modules=None, safe_mode=True, module_options=…, dry_run=False, ci=None)`, `run_plan(plan, *, modules=("functional",), spec_root=None)`, `report(run_id=None, *, latest=False)`, `verify_fix(run_id, suggestion)`. Every method has an `async_<name>` counterpart; sync forms are `asyncio.run(self.async_<name>(...))` so the implementation lives exactly once.
- **Public result models** (`sentinelqa._models`): `AuditResult` (Pydantic, frozen, `extra="forbid"`, `SCHEMA_VERSION` pinned to `RUN_SCHEMA_VERSION`) with derived views `passed` / `failures` / `blockers` / `findings_by_severity(...)` / `findings_by_module(...)` and `to_agent_messages()`; `QualityGate.from_config(policy)` and `Policy.from_config(root)` re-expose config posture as immutable views.
- **Public surface modules** (only these are stable contract): `sentinelqa`, `sentinelqa.errors`, `sentinelqa.agent`. The `__all__` list is locked by `packages/python-sdk/api-snapshot.json`; CI gate `tests/unit/sdk/test_api_snapshot.py` fails on drift. Regenerate via `make sdk-api-snapshot` and follow `packages/python-sdk/__deprecation_policy.md` for any breaking change.
- **Errors** (`sentinelqa.errors`): re-exports `SentinelError`, `ConfigError` (+ `ConfigFileNotFoundError` / `ConfigSchemaError` / `ConfigSecretInlineError`), `UnsafeTargetError` (+ `UnknownHostError` / `DestructiveWithoutProofError` / `ForbiddenFlagError`), `DependencyMissingError`, `TestExecutionError`, `QualityGateFailedError`. `from_dict(agent_message)` reconstructs the most specific subclass for a given code; round-trip preserves `code`, `exit_code`, `message`, `suggested_fix`, `context`.
- **Agent messages** (`sentinelqa.agent`): `format(messages, *, format="ndjson"|"jsonl"|"list")` serializes a stream of dicts deterministically (sorted keys, no ASCII escapes). `Finding.to_agent_message()` and `RepairSuggestion.to_agent_message()` produce stable, redacted dicts (versioned by `AGENT_MESSAGE_SCHEMA_VERSION`). `AuditResult.to_agent_messages()` emits a fixed sequence: `run_summary` → one `finding` per finding → `blocker_summary` → `next_actions`.
- **Lazy import**: `import sentinelqa` stays well under the 200 ms target (measured: ~80 ms) because heavy submodules (orchestrator, planner, discovery, generator, runner, reporter) are imported only when a facade method needs them.
- **Internals**: `sentinelqa._internal/` and any `_`-prefixed name is non-public; it may change without a deprecation window.
- **Deferred capability**: `Sentinel.verify_fix` raises `NotImplementedError` with a Phase-20 pointer until the Healer module ships. The signature is public so callers can write against it today (CLAUDE.md §37 permits `NotImplementedError` for interfaces awaiting concrete adapters).

ADR-0021 owns the rationale and the surface gate.

---

## 15. TypeScript Runtime Specification

### 15.1 Purpose

The TypeScript runtime executes generated Playwright tests and module-specific browser workflows. It ships as a single workspace package — `@sentinelqa/ts-runtime` — with three subpath exports consumed by later phases: `./playwright` (generated-test helpers + `sentinelTest`), `./protocol` (JSONL event types + emitter/parser), and `./locators` (semantic-first strategy chain + brittleness audit). The Python ↔ TypeScript boundary is owned by ADR-0009.

### 15.2 Example helper

```ts
import { sentinelTest as test, expect } from "@sentinelqa/ts-runtime/playwright";
import { sentinelStep, captureEvidence } from "@sentinelqa/ts-runtime/playwright";

test("user can create a project", async ({ page, sentinel }) => {
  await sentinelStep(sentinel, "login", async () => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(process.env.TEST_USER_EMAIL!);
    await page.getByLabel("Password").fill(process.env.TEST_USER_PASSWORD!);
    await page.getByRole("button", { name: /sign in/i }).click();
  });

  await sentinelStep(sentinel, "create project", async () => {
    await page.getByRole("button", { name: /new project/i }).click();
    await page.getByLabel("Project name").fill("Sentinel Test Project");
    await page.getByRole("button", { name: /create/i }).click();
    await expect(page.getByText("Sentinel Test Project")).toBeVisible();
  });

  await captureEvidence(sentinel, page, "project-created");
});
```

### 15.3 `sentinel-ts` binary contract

Python orchestrates `sentinel-ts` (resolved to `dist/cli.js`) over stdout as the canonical Playwright launcher. Surfaces shipped in Phase 04:

| Command            | Purpose                                                                                                                                                                                                                                                                                |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--help` / `-h`    | Print the usage block.                                                                                                                                                                                                                                                                 |
| `--version` / `-V` | Print `@sentinelqa/ts-runtime <semver>`.                                                                                                                                                                                                                                               |
| `run`              | `--input <run-config.json>` invokes Playwright with the custom reporter and streams JSONL.                                                                                                                                                                                             |
| `list-tests`       | `--pattern <glob>` lists spec files; skips `node_modules` / `dist` / `.git` in every result.                                                                                                                                                                                           |
| `audit-locators`   | `--file <path>` runs the brittleness audit on a generated spec.                                                                                                                                                                                                                        |
| `audit-a11y`       | `--input <run-config.json>` runs axe-core + keyboard + landmark + accessible-name checks per route.                                                                                                                                                                                    |
| `audit-perf`       | `--input <run-config.json>` runs synthetic perf checks (LCP/CLS/INP/TTFB + API latency + bundle/CPU + nav stability).                                                                                                                                                                  |
| `discover`         | `--config <path|->` Playwright-driven crawl backend (Phase 17 task 07, ADR-0010). Emits `discovery.page` / `discovery.endpoint` events.                                                                                                                                                |
| `validate-helpers` | Sanity-check that the package loads, the redaction ruleset is readable, and helpers export.                                                                                                                                                                                            |

Deterministic exit codes: `0` all pass, `1` ≥1 test failed/timed out, `2` Playwright crashed / config invalid / spawn failed / unknown command or flag, `7` programmer error (sync dispatch hit an async command). These map onto PRD §13.2 / CLAUDE §13.

### 15.4 JSONL event protocol

The runtime emits one JSON event per stdout line, parsed by Python's `engine/orchestrator/ts_bridge.py`. Every event carries the envelope `{type, schema_version, seq, ts}`; the discriminator is `type` and the schema covers sixteen kinds: `run.start`, `run.end`, `test.start`, `test.end`, `step.start`, `step.end`, `evidence`, `network.request`, `network.response`, `console`, `dom.snapshot`, `module.event`, `log`, `error`, plus the Phase 17 task 07 additions `discovery.page` and `discovery.endpoint` (Playwright discovery backend). The wire format is locked by `packages/shared-schema/ts-events.schema.json` (Draft 2020-12). A canonical fixture (`tests/golden/ts-events/sample.jsonl`) drives the cross-language parity tests; schema bumps require a successor ADR (ADR-0009 owns the rules).

### 15.5 Evidence capture defaults

`sentinelTest` and `sentinel-ts run` apply the CLAUDE §21 defaults uniformly: `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`, `video: 'retain-on-failure'`. The reporter translates Playwright trace/screenshot/video attachments into `evidence` events; opt-in helpers add `dom.snapshot` (with an AX-tree hash for the Healer in Phase 20), redacted browser-console events (`console`), redacted network events (`network.request` / `network.response`), and HAR via `harConfig(ctx)` when the run config sets `evidence.har: true`. The "failure always emits evidence" contract is pinned by an integration test.

### 15.6 Semantic locator strategy

`@sentinelqa/ts-runtime/locators` exports the strategy chain used by Phase 07 (Generator) and Phase 20 (Healer): `getByRole → getByLabel → getByPlaceholder → getByText → getByTestId → getByAltText → getByTitle`. `bestLocator(page, target)` returns the first strategy whose locator matches exactly one element. `describeLocator(locator)` captures role, accessible name, text, ARIA-landmark ancestors, and `tagName` for Healer repairs. `auditLocatorBrittleness(spec)` is a static analysis (via ts-morph) that flags brittle patterns (`:nth-of-type`, raw XPath, deeply nested div soup, class-prefix matchers) so generated specs satisfy CLAUDE §21 before they reach disk.

### 15.7 Safety boundary and redaction symmetry

The TS runtime never imports stealth, evasion, fingerprint-spoofing, CAPTCHA-bypass, or proxy-rotation libraries (CLAUDE §6, PRD §2). Redaction is mirrored from Python via `packages/shared-schema/redaction-rules.json` (Python is the source of truth; `scripts/export-redaction-rules.py --check` is the drift gate). A 19-record byte-parity fixture asserts string / recursive-value / header outputs match across both languages. Every JSONL line and every on-disk artifact (DOM snapshots, network/console logs, error stacks) passes through `redact()` before write.

**URL redaction — behavioural contract, not byte-form parity.** `redact_url` (Python, `urllib.parse.urlparse`) preserves the original hostname case; `redactUrl` (TS, `URL`) canonicalises the hostname to lower case. The two implementations therefore cannot guarantee byte-identical output for arbitrary URLs. The contract is instead behavioural and is enforced on both sides:

- userinfo is stripped (no `user:pass@` ever appears in the output);
- secret-shaped query keys (`token`, `access_token`, …) are replaced with the marker `[REDACTED:url_token]`;
- non-secret query values are still passed through the value-level redactor.

Any future Python ↔ TS consumer that needs to *compare* URLs across the boundary must normalise both sides (lowercase the hostname, sort query parameters) before comparison.

**LLM-provider redaction (Phase 30, ADR-0042).** Every outbound LLM request body and inbound LLM response body passes through `engine.llm.redaction.redact_request` / `redact_response` before reaching the audit log. The summarizers collapse `messages` / `contents` / `system` / `prompt` fields to count-and-redaction markers by default; the full prompt and response text never touch the audit log unless the caller explicitly opts in via `LlmRedactionPolicy(include_prompts_in_audit=True)`. API keys are read from env vars at call time, attached to the HTTP request via the provider's auth header, and are NEVER inlined into any log line. This Python-only invariant is consistent with §15.7 — the TS runtime never calls remote LLMs directly.

---

## 16. MCP / LLM Tool Interface

### 16.1 Tools

```json
[
  "sentinel.discover",
  "sentinel.plan",
  "sentinel.generate_tests",
  "sentinel.run_tests",
  "sentinel.audit",
  "sentinel.security_audit",
  "sentinel.performance_audit",
  "sentinel.accessibility_audit",
  "sentinel.read_report",
  "sentinel.explain_failure",
  "sentinel.suggest_fix",
  "sentinel.verify_fix"
]
```

### 16.2 Example request

```json
{
  "tool": "sentinel.audit",
  "arguments": {
    "url": "http://localhost:3000",
    "modules": ["functional", "security", "performance"],
    "safe_mode": true,
    "output": "json"
  }
}
```

### 16.3 Example response

```json
{
  "passed": false,
  "quality_score": 72,
  "release_decision": "blocked",
  "critical_findings": [
    {
      "id": "SEC-001",
      "title": "Session cookie missing Secure flag",
      "severity": "high",
      "evidence": ["network:cookies"],
      "suggested_fix": "Set Secure, HttpOnly, and SameSite flags on session cookie."
    }
  ]
}
```

### 16.4 MVP delivery (Phase 18)

Phase 18 ships the production MCP surface (PRD §16, ADR-0023).

- **Package:** `packages/mcp-server/` (`sentinelqa-mcp` on PyPI). Pure
  Python; no runtime dependencies beyond `sentinelqa`, `sentinelqa-engine`,
  and Pydantic 2.10.x. The package implements the MCP JSON-RPC 2.0
  base transport in stdlib so the Pydantic pin and the Phase-01..16
  schema set stay byte-identical (CLAUDE.md §35, see ADR-0023 for the
  full rationale).
- **Wire protocol:** JSON-RPC 2.0 over NDJSON-framed stdio. MCP
  protocol version `2024-11-05` only — newer versions are rejected at
  `initialize`. Implemented methods: `initialize`, `notifications/initialized`,
  `tools/list`, `tools/call`, `ping`. `notifications/cancelled` is
  observed.
- **Tools:** every PRD §16.1 tool registered (`discover`, `plan`,
  `generate_tests`, `run_tests`, `audit`, `security_audit`,
  `performance_audit`, `accessibility_audit`, `read_report`,
  `explain_failure`, `suggest_fix`, `verify_fix`) plus a `ping` health
  check. Each tool's args are validated against a Draft 2020-12 JSON
  Schema declared in its `ToolSpec`; read-only tools advertise
  `_meta.read_only=true` in `tools/list`.
- **AgentEnvelope:** every tool response — success or failure — uses
  the shape `{ schema_version, tool, result, errors, evidence_refs }`.
  Locked by `packages/shared-schema/agent-envelope.schema.json` and the
  byte-stable golden under `tests/golden/mcp/expected/ping_success.json`.
  `AGENT_ENVELOPE_SCHEMA_VERSION="1"`.
- **Safety contract (CLAUDE.md §6, §15):** every URL-bearing tool runs
  `SafetyPolicy.enforce` via `sentinelqa_mcp.tools._safety.enforce_url`
  before any SDK call. An AST guard at
  `tests/security/test_mcp_safety.py` enforces this on every CI run.
  Unsafe targets surface as envelope errors (`code=UNSAFE_TARGET`,
  `exit_code=4`); there is no MCP argument that disables the safety
  boundary. Destructive checks require the loaded config to opt in
  AND supply a valid `target.proof_of_authorization`.
- **`sentinel.verify_fix` decision matrix** (ADR-0023): re-runs the
  prior run's audit against the current working tree and diffs findings
  by stable fingerprint (`module`|`category`|`title`|`location.file`|`location.selector`).
  Decisions: `fix_verified` (target gone + no findings),
  `still_failing` (target still present + no regressions),
  `regressed` (target still present + new regressions), or `partial`
  (any other outcome — e.g. target gone but other findings linger).
- **CLI:** `sentinel mcp` replaces the Phase 02 stub.
  Options: `--stdio` (default), `--http <PORT>` (loopback only — refuses
  non-loopback binds with exit 4), `--config <PATH>`, `--log-level
  <LEVEL>`. Exit codes 0 / 2 / 4 / 7.
- **Read-only file access:** `sentinel.read_report` reads a single
  top-level artifact under a run directory. Path traversal (`..`,
  multi-segment paths) is rejected with exit code 2. Files larger than
  256 KiB are truncated. Binary files are returned as hex
  (`encoding: "hex"`).
- **Logs go to stderr only** for the lifetime of the server — stdout is
  reserved for MCP wire bytes (CLAUDE.md §13).

The `sentinel.verify_fix` MCP tool's _agent-observable_ loop is
complete in Phase 18. The Phase-16 `Sentinel.verify_fix` SDK method
still raises `NotImplementedError` (CLAUDE.md §37) because the
Healer's apply-fix logic lands in Phase 20. The Phase-18 contract is
agent-first: the agent applies the fix; the MCP tool verifies.

---

## 17. Configuration Specification

### 17.1 `sentinel.config.yaml`

```yaml
version: 1

project:
  name: example-app
  framework: nextjs
  package_manager: pnpm

source:
  root: .
  include:
    - app
    - pages
    - src
  exclude:
    - node_modules
    - .next
    - dist

target:
  base_url: http://localhost:3000
  allowed_hosts:
    - localhost
    - 127.0.0.1
    - staging.example.com

auth:
  # Choose one of: test_user | api_key | oauth | browser_session | none.
  # `browser_session` (Phase 31, ADR-0043) replays a real, human-captured
  # Playwright `storage_state` from the encrypted vault for apps behind
  # SSO / MFA / consumer-LLM web logins.
  strategy: test_user
  login_url: /login
  username_env: TEST_USER_EMAIL
  password_env: TEST_USER_PASSWORD
  # For `strategy: browser_session` only — the vault entry name created
  # by `sentinel auth login <name> --url <login-url>`. The host is taken
  # from `target.base_url`; SentinelQA refuses to surface a session
  # whose recorded host is not in `target.allowed_hosts`.
  # session_name: github-myorg

modules:
  functional: true
  api: true
  accessibility: true
  performance: true
  visual: true
  security: true
  chaos: false
  llm_audit: true

security:
  mode: safe
  destructive_tests: false
  max_requests_per_second: 5
  allowed_payload_level: low

performance:
  budgets:
    lcp_ms: 2500
    cls: 0.1
    inp_ms: 200
    api_p95_ms: 500
    js_total_kb: 500

visual:
  baselines_dir: .sentinel/baselines
  threshold: 0.02
  mask_dynamic_content: true

policy:
  min_quality_score: 85
  block_on_critical: true
  block_on_high_security: true
  max_flake_rate: 0.03

report:
  output_dir: .sentinel/reports
  formats:
    - html
    - json
    - junit
    - sarif

# Multi-provider LLM (Phase 30, ADR-0042). The block is optional —
# defaults give every consumer the `null` provider, no API calls, no
# spend. Per-caller blocks (`planner.llm.*`, `analyzer.llm.*`) remain
# the fine-grained surface; this block centralizes the provider list,
# shared budget, and rate-limit.
llm:
  default_provider: null  # one of: null, anthropic, openai, gemini,
                          #         ollama, azure_openai, vertex,
                          #         mistral, groq, openrouter
  providers:
    anthropic:
      api_key_env: ANTHROPIC_API_KEY
      models:
        planner: claude-3-5-sonnet-20241022
        analyzer: claude-3-5-haiku-20241022
    openai:
      api_key_env: OPENAI_API_KEY
      models:
        planner: gpt-4o-mini
    gemini:
      api_key_env: GEMINI_API_KEY
      models:
        planner: gemini-1.5-flash
    ollama:
      host: http://localhost:11434
      models:
        planner: qwen2.5-coder:7b
    azure_openai:
      api_key_env: AZURE_OPENAI_API_KEY
      azure_resource: my-resource
      azure_deployment: gpt4o-prod
      azure_api_version: 2024-08-01-preview
    vertex:
      api_key_env: GOOGLE_APPLICATION_CREDENTIALS
      vertex_project: my-gcp-project
      vertex_region: us-central1
    mistral:
      api_key_env: MISTRAL_API_KEY
    groq:
      api_key_env: GROQ_API_KEY
    openrouter:
      api_key_env: OPENROUTER_API_KEY
  budget:
    max_usd_per_run: 0.50
    max_usd_planner: 0.30   # optional sub-cap
    max_usd_analyzer: 0.15  # optional sub-cap
    max_usd_healer: 0.05    # optional sub-cap
  rate_limit:
    requests_per_minute: 60
```

---

## 18. Data Model

### 18.1 Core entities

```text
Project
Target
DiscoveryGraph
Route
Element
Form
ApiEndpoint
Flow
TestCase
TestRun
ModuleResult
Finding
Evidence
QualityScore
PolicyDecision
RepairSuggestion
```

### 18.2 Finding schema

```json
{
  "id": "A11Y-004",
  "module": "accessibility",
  "severity": "medium",
  "title": "Button missing accessible name",
  "description": "A button on /dashboard has no accessible label.",
  "location": {
    "route": "/dashboard",
    "selector": "button:nth-of-type(3)"
  },
  "evidence": [
    {
      "type": "screenshot",
      "path": ".sentinel/artifacts/a11y-004.png"
    }
  ],
  "reproduction_steps": [
    "Open /dashboard",
    "Inspect the icon-only button in the header"
  ],
  "suggested_fix": "Add aria-label or visible text to the button.",
  "confidence": 0.93
}
```

---

## 19. Quality Scoring Model

### 19.1 Score components

| Component | Default weight |
|---|---:|
| Functional | 30% |
| Security | 20% |
| Performance | 15% |
| Accessibility | 10% |
| API | 10% |
| Visual | 5% |
| LLM-code audit | 5% |
| Flake risk | 5% |

### 19.2 Severity penalties

| Severity | Penalty |
|---|---:|
| Critical | Blocks release |
| High | -10 to -25 |
| Medium | -3 to -10 |
| Low | -1 to -3 |
| Info | 0 |

### 19.3 Release decisions

```text
pass
pass_with_warnings
blocked
inconclusive
unsafe_target_rejected
```

### 19.4 Policy examples

```yaml
policy:
  min_quality_score: 85
  block_on_critical: true
  block_on_high_security: true
  allow_medium_a11y: true
  max_failed_p1_flows: 0
```

### 19.5 MVP delivery (Phase 14)

Status: **Stable**.

Phase 14 ships the canonical scoring pipeline behind ADR-0019. The
implementation lives in `engine/scoring/` and runs as two lifecycle
hooks the orchestrator registers automatically:

- `engine.scoring.model.compute_score(...)` — pure function from
  `(findings, module_results, policy)` to
  `engine.domain.quality_score.QualityScore`. Per-axis component
  scores are `max(0, 100 - Σ severity_penalty(finding))`; the
  `flake_risk` axis is derived from `ModuleResult.metrics["flake_rate"]`
  via `100 * (1 - min(1, avg / policy.max_flake_rate))`. The
  aggregate `total` is the weighted average of the eight PRD §19.1
  axes clamped to `[0, 100]` and rounded half-to-even to 2 decimals
  for byte-stable JSON.
- `engine.scoring.blockers.compute_blockers(...)` — applies the
  CLAUDE.md §25 blocker rules (`critical_finding`, `security_high`,
  `p0_flow_failed`, `too_many_p1_failures`). P0 / P1 detection
  parses the `@p0..p3` tag out of the finding title (Phase 10
  generated specs embed it there); the helper falls back to the
  description if the title doesn't carry the tag.
- `engine.scoring.decision.decide(...)` — produces the typed
  `engine.domain.policy_decision.PolicyDecision`. Priority: unsafe
  → incomplete/dry-run (`inconclusive`) → blockers (`blocked`) →
  score < `min_quality_score` (`blocked`) → any medium finding
  (`pass_with_warnings`) → otherwise `pass`.
- `engine.scoring.policy_gate.register_scoring_hooks(...)` — wires
  the two hooks onto `LifecyclePhase.CALCULATE_QUALITY_SCORE` and
  `LifecyclePhase.APPLY_QUALITY_GATES`. The gate hook flips
  `quality_gate_passed = False` only when the decision is `blocked`;
  `_finalize_status` then stamps the run as `failed`, which the CLI
  maps to exit code 1 (`EXIT_QUALITY_GATE_FAILED`).

New config fields under `policy:` expose the severity-penalty
midpoints so projects can be stricter or looser without forking the
scoring code:

- `severity_penalty_high: float` (default 17.5, range 10..25).
- `severity_penalty_medium: float` (default 6.5, range 3..10).
- `severity_penalty_low: float` (default 2.0, range 1..3).

Critical findings always carry a fixed penalty of 30 so the numeric
score still reflects severity even when `block_on_critical` is the
dominant gating signal.

The Phase-15 stub for `sentinel report` is replaced by a real command
that implements the **explain path only**: `sentinel report
--explain-score [--run-id RUN-…] [--latest] [--runs-root .sentinel/runs]`
prints the per-axis math + severity penalties + blockers + policy
thresholds to stdout (human or JSON), and writes a deterministic
`score-explanation.md` next to the source `score.json`. Calling
`sentinel report` without `--explain-score` still surfaces a
"lands in Phase 15" error (exit 7) — no fake completion.

Reproducibility is guarded by two complementary tests:

- `tests/property/scoring/test_reproducibility.py` (hypothesis, slow
  tier, 5000 examples) — random findings + module results + policy
  must always produce byte-identical `score.json`.
- `tests/integration/scoring/test_replay.py` — three canonical
  scenarios (`clean`, `mixed`, `blocked`) are byte-compared against
  committed expected files under
  `tests/integration/scoring/expected/`.

ADR-0019 records the rationale, including the P0 / P1 tag-based MVP
shortcut and the plan to retire it when a future phase adds a
`priority` field to the Finding model.

---

## 20. Evidence and Reporting Requirements

Every failure must have at least one evidence artifact.

Evidence types:

- Screenshot.
- Video.
- Playwright trace.
- HAR.
- Console log.
- Network log.
- DOM snapshot.
- Stack trace.
- API request/response sample with secrets redacted.
- Source code reference.

Sensitive values must be redacted:

- Passwords.
- Tokens.
- API keys.
- Cookies.
- Authorization headers.
- PII.

### 20.1 Persisted artifacts (Phase 03)

Every run writes the artifacts below into `.sentinel/runs/<run-id>/`. Wire
formats are versioned via a top-level `schema_version` field and locked
by JSON Schemas under `packages/shared-schema/`. ADR-0008 captures the
design.

| Artifact          | Schema                                                | Notes                                                                                  |
| ----------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `run.json`        | `packages/shared-schema/run.schema.json`              | Top-level run summary. Always written. SHA-256 `config_digest`.                        |
| `findings.json`   | `packages/shared-schema/findings.schema.json`         | Envelope `{schema_version, run_id, generated_at, count, findings[]}`.                  |
| `score.json`      | `packages/shared-schema/score.schema.json`            | Reproducible quality score; `total` rounded to 2 decimals.                             |
| `junit.xml`       | `packages/shared-schema/external/junit.xsd`           | Surefire subset for CI ingestion.                                                       |
| `sarif.json`      | `packages/shared-schema/external/sarif-2.1.0.json`    | Vendored official OASIS schema; severity → SARIF level: critical/high→error, medium→warning, low/info→note. |
| `report.md`       | _(no formal schema; deterministic Markdown)_          | PR-comment friendly summary; user input is backslash-escaped.                          |
| `audit.log`       | JSONL, one event per line, redacted                   | Records safety decisions and one `artifact_emitted` event per emitted report.          |
| `config.snapshot.yaml` | `packages/shared-schema/schemas/*.schema.json`    | Per-domain pydantic schemas generated by `make schemas`.                               |

The reporter is implemented as a single dispatcher
(`engine/reporter/__init__.py`) that the run lifecycle invokes during
the `generate_reports` step. `config.report.formats` selects which
optional formats are produced; `run.json` is always written. The `json`
format expands to the run/findings/score trio. `html` is a Phase-15
placeholder (no-op for now).

### 20.2 Finding evidence requirement

`findings.json` rejects any finding with `severity ∈ {critical, high,
medium}` that has no evidence artifact (`L-FND-004`). A non-blocking
vague-finding linter also flags titles shorter than 8 characters,
descriptions matching banned phrases without concrete specifics, and
empty descriptions.

### 20.3 Schema drift guard

Every committed `*.schema.json` is validated against its meta-schema in
CI. Every emitted artifact has a byte-locked golden under
`tests/golden/reports/`. Regeneration goes through `make
update-goldens`, which prompts for confirmation unless `FORCE=1` is set;
the diff in the follow-up commit is the audit trail. Hypothesis property
tests (slow tier) generate randomized findings and prove every writer
emits schema-valid output.

---

## 21. CI/CD Requirements

### 21.1 GitHub Action

```yaml
name: SentinelQA

on:
  pull_request:
  push:
    branches: [main]

jobs:
  qa:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - uses: actions/setup-python@v5
      - run: npm install
      - run: npx playwright install --with-deps
      - run: pip install sentinelqa
      - run: sentinel ci --url ${{ secrets.PREVIEW_URL }} --diff origin/main...HEAD
```

### 21.2 PR comment

The PR comment should include:

- Quality score.
- Release decision.
- Critical findings.
- Changed flows tested.
- Links to artifacts.
- Suggested next steps.

### 21.3 CI modes

- `fast`: smoke + impacted tests.
- `standard`: impacted + required gates.
- `full`: full regression.
- `nightly`: full + chaos + extended security.
- `release`: full + strict policy.

### 21.4 MVP delivery (Phase 17)

Phase 17 lights up the CI surface as a thin preset layer over the existing lifecycle (ADR-0022):

- **`engine/ci/modes.py`** — `apply_mode(config, mode, fail_under=None)` returns `(effective_config, ModePlan)`. Each mode is a recipe over `modules`, `grep` (Playwright tag filter), and `policy_overrides`. `release` raises `policy.min_quality_score` to `max(config, 90)`; `--fail-under` always wins over the mode default. Modes intersect with the user's enabled module set so the config remains authoritative for the safety boundary.
- **`engine/ci/diff_aware.py`** — `select_from_files(diff_range, changed_files)` is a pure helper that walks the file list with deterministic framework-shape heuristics (Next.js App Router / Pages Router, Vite `src/routes/` and `src/pages/`, OpenAPI / GraphQL schemas, API routes). Broad-impact files (`pnpm-lock.yaml`, `next.config.ts`, `Dockerfile`, etc.) and high-volume diffs (> 50 files) force fallback to full mode. The smoke tag (`@p0`) is always present in `grep()`. `select_from_git` shells out to `git diff --name-only <range>` for the CLI path; the function is testable without git via the `runner` injection point.
- **`sentinel ci`** — the Phase-02 stub is replaced. Options: `--url`, `--mode` (default `standard`), `--diff` (e.g. `origin/main...HEAD`), `--fail-under`, `--grep`, `--output`. The command always forces `--ci=True`, writes a deterministic `<run-dir>/ci.json` sidecar with the mode, diff range, resolved selection, and policy overrides, and threads the resolved grep into `module_options["functional"]["grep"]`. Exit codes follow PRD §13.2 (0 passed, 1 quality gate failed, 2 config / invalid mode, 4 unsafe target, 5 git missing for `--diff`, 6 incomplete).
- **GitHub composite Action** — `integrations/github/action.yml` ships the composite Action with inputs `url` (required), `config`, `mode`, `fail-under`, `diff`, `python-version`, `node-version`, `sentinelqa-version`, `install-playwright`, `upload-artifacts`, `upload-sarif`, `artifact-name`, `artifact-retention-days`, `working-directory`. Outputs: `quality-score`, `release-decision`, `report-html-url` (all read from the latest `score.json`). Uses `actions/upload-artifact@v4` for the run artifacts and `github/codeql-action/upload-sarif@v3` for code-scanning ingest. A reusable workflow `integrations/github/workflows/sentinel-pr.yml` calls the Action and posts the PR comment.
- **GitLab template** — `integrations/gitlab/.gitlab-ci.sentinel.yml` declares a `.sentinelqa` job template extendable via `extends: .sentinelqa`. Variables: `SENTINELQA_URL` (required), `SENTINELQA_MODE`, `SENTINELQA_DIFF`, `SENTINELQA_FAIL_UNDER`, `SENTINELQA_VERSION`, `PYTHON_VERSION`, `NODE_VERSION`. Caches pip + pnpm + node_modules. Refuses to audit an empty URL (exits 4). Uploads `run.json`, `findings.json`, `score.json`, `report.html`, `report.md`, `sarif.json`, `junit.xml`, traces / screenshots / videos for 14 days; JUnit XML drives GitLab's native test reporting; `findings.json` is consumed as a Code Quality report.
- **PR / MR comment posters** — `integrations/github/post_pr_comment.py` and `integrations/gitlab/post_mr_note.py`. Both use `urllib` (no `requests` dep, per CLAUDE.md §35), upsert via the `<!-- sentinelqa:pr-comment -->` anchor (shared with the Phase 15 reporter), read tokens from env vars only (never logged), and retry with exponential backoff on 429 / 5xx (honors `Retry-After`). Refuses to post a body that doesn't begin with the SentinelQA anchor — defense against accidental empty / mis-routed posts.

### 21.5 Phase 25 integrations (remote runners, notifications, issue creation)

Phase 25 lights up the rest of `integrations/` (ADR-0030). Every adapter is off by default, reads credentials from environment variables at call time, and never logs them (CLAUDE.md §33). The engine does NOT import these adapters directly (CLAUDE.md §7); operators opt in either via CLI / external workflow or by packaging an adapter as a Phase-24 plugin.

- **Shared HTTP client** — `integrations/_http.py` exposes `HttpClient` (stdlib `urllib` only), `AuthHeader` (Bearer / Basic / custom factory), `RetrySpec` (exponential backoff on `{429, 502, 503, 504}` honoring `Retry-After`), and `redact_url` / `safe_reason` helpers. Every Phase 25 adapter shares this client so retry, redaction, and timeout behaviour are identical across services.
- **`integrations/browserstack/runner.py`** — `BrowserStackRunner` shaped like the SDK `RunnerPlugin` Protocol (`sentinelqa.plugins.RunnerPlugin`). `map_capabilities()` is a pure function over a SentinelQA-shaped invocation; `run(invocation, context)` creates a session via the BrowserStack Automate API and best-effort uploads any `trace_paths`. Quota-exhaustion (HTTP 429) surfaces in the outcome dict as `status="quota_exceeded"` so callers can fall back to the local runner. Env vars: `BROWSERSTACK_USERNAME`, `BROWSERSTACK_ACCESS_KEY`.
- **`integrations/saucelabs/runner.py`** — `SauceLabsRunner` same shape and contract as the BrowserStack adapter. Region defaults to `us-west-1`; `eu-central-1` and `apac-southeast-1` are also supported. Env vars: `SAUCE_USERNAME`, `SAUCE_ACCESS_KEY`.
- **`integrations/slack/poster.py`** — `SlackPoster.post(payload)` posts the Phase 15.06 Block Kit dict to an incoming webhook. A `SlackWebhookDeduper` keyed on `sha256(webhook URL + payload)` suppresses double-posts within a 5-minute window. The webhook URL is read from `SLACK_WEBHOOK_URL` at call time and is doubly-redacted in error / log messages (query string + path after `/services/`). CLI entry: `python -m integrations.slack.poster --payload <file>`.
- **`sentinel report --notify slack`** — the Phase 15 re-render CLI gains a `--notify <channel>` flag (repeatable). `slack` is the only channel wired by Phase 25; unknown channels exit 2. `--notify slack` reads `SLACK_WEBHOOK_URL` from the environment and calls `integrations.slack.post_payload(...)` with the rendered Block Kit payload + a `<run-dir>/slack-dedup.json` cache. JSON mode keeps stdout valid (the success line is suppressed when `--json` is on).
- **`integrations/github/status.py`** — `post_commit_status(repo, sha, state, description, target_url, context, client)` posts a single commit status (`pending|success|failure|error`). Description is clipped to GitHub's 140-char limit. CLI entry: `python -m integrations.github.status`. Default `context` is `sentinelqa/quality-gate`. Env var: `GITHUB_TOKEN`.
- **`integrations/github/issue.py`** — `create_issue_for_finding(repo, finding, client, auto_create=False)` opens an issue tracking the finding. The issue title carries a stable `[sentinelqa:FND-XXX]` anchor so re-invocations upsert rather than spam. **Auto-create is off by default**: callers must pass `auto_create=True` AND set `policy.github.auto_create_issue: true`. Issue bodies pass through `engine.policy.redaction.redact` before they leave the host.
- **`integrations/gitlab/status.py`** — `post_commit_status(api_url, project, sha, state, description, target_url, name, client)` posts a pipeline commit status (`pending|running|success|failed|canceled`). Project paths are URL-encoded so namespaced repos work without caller-side encoding. Description is clipped to GitLab's 255-char limit. CLI entry: `python -m integrations.gitlab.status`. Env var: `GITLAB_TOKEN`.
- **`integrations/jira/issue.py`** — `create_issue(credentials, project_key, finding, issue_type, client)` opens a Jira issue. Severity → priority mapping is fixed (critical → Highest, high → High, medium → Medium, low → Low, info → Lowest). HTTPS base-URL only. Env vars: `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`.
- **`integrations/linear/issue.py`** — `create_issue(credentials, team_id, finding, client)` opens a Linear issue via GraphQL (`issueCreate` mutation). Severity → priority mapping: critical=1 (Urgent), high=2, medium=3, low=4, info=0. Env var: `LINEAR_API_KEY`.
- **Config blocks** — `policy.github.auto_create_issue: bool` (default `false`) and `policy.integrations.{slack, jira, linear}` cover the new feature gates. `sentinel.config.yaml.example` documents the surface; every block defaults to off.
- **Credential-leak guard** — `tests/integration/integrations/test_credential_leak_guard.py` runs on every CI pass and FAILS if any Phase 25 secret env var is non-empty (`BROWSERSTACK_USERNAME/_ACCESS_KEY`, `SAUCE_USERNAME/_ACCESS_KEY`, `SLACK_WEBHOOK_URL`, `JIRA_USER_EMAIL/_API_TOKEN`, `LINEAR_API_KEY`). `GITHUB_TOKEN` is explicitly excluded because the Phase-17 PR-comment poster legitimately consumes it.

ADR-0030 owns the rationale, including the explicit rejection of pulling `requests` into the dependency set (CLAUDE.md §35) and the decision to keep auto-issue creation off the audit lifecycle until a follow-up ADR.

## 22. Plugin Architecture

### 22.1 Plugin types

- Discovery plugin.
- Scanner plugin.
- Runner plugin.
- Reporter plugin.
- Policy plugin.
- Auth plugin.
- Data fixture plugin.
- Cloud execution plugin.

### 22.2 Plugin interface

```python
from sentinelqa.plugins import ScannerPlugin, ScanContext, ModuleResult

class MyScanner(ScannerPlugin):
    name = "my_scanner"
    version = "1.0.0"

    def run(self, context: ScanContext) -> ModuleResult:
        ...
```

### 22.3 Plugin requirements

- Sandboxed execution where possible.
- Versioned contracts.
- Capability declaration.
- Permission declaration.
- Safe defaults.

### 22.4 MVP delivery (Phase 24)

Phase 24 ships the plugin architecture end-to-end under ADR-0029.

- **SDK public surface** — `packages/python-sdk/src/sentinelqa/plugins.py`
  defines `PROTOCOL_VERSION = "1.0.0"`, the `ENTRY_POINT_GROUP =
  "sentinelqa.plugins"` constant, the `PluginContext` runtime
  Protocol, and eight `@runtime_checkable` Protocols
  (`DiscoveryPlugin`, `ScannerPlugin`, `RunnerPlugin`,
  `ReporterPlugin`, `PolicyPlugin`, `AuthPlugin`,
  `DataFixturePlugin`, `CloudExecutionPlugin`). Every Protocol
  declares the same four required attributes (`name`, `version`,
  `capabilities`, `permissions`) plus a `kind` discriminator and a
  per-kind method. The surface is part of the SDK API snapshot
  (`packages/python-sdk/api-snapshot.json` now lists
  `sentinelqa.plugins` as the fourth public module).

- **Manifest wire format** —
  `packages/shared-schema/plugin-manifest.schema.json` (Draft 2020-12,
  `x-sentinelqa-schema-version "1"`) is the wire format plugin
  authors publish. `engine.plugins.manifest.Manifest` is the runtime
  Pydantic equivalent; a drift guard
  (`tests/integration/plugins/test_manifest_schema.py`) proves the
  two agree on accept and reject paths.

- **Loader** — `engine.plugins.discover()` iterates
  `importlib.metadata.entry_points(group="sentinelqa.plugins")`,
  synthesises a manifest from each candidate's class-level
  attributes, validates it, rejects forbidden capabilities (CLAUDE
  §6 via
  `engine.policy.forbidden_features.FORBIDDEN_CAPABILITIES`), checks
  semver compatibility via `packaging.specifiers`, and verifies
  `isinstance(obj, PLUGIN_PROTOCOLS[kind])`. Failures log + skip; a
  broken plugin never crashes the run.

- **Capabilities + permissions** — capabilities are free-form tags
  (rejected only against the forbidden list); permissions follow the
  grammar `<group>.<verb>[:<scope>]` and must be on the host
  allow-list (`fs.read`, `fs.write:.sentinel/runs`, `network.outbound`,
  `subprocess.spawn`, plus scoped `fs.read:<path>` and
  `env.read:<NAME>`). Unscoped `fs.write` is explicitly forbidden.

- **Runtime context** — `engine.plugins.runtime.PluginContextImpl`
  hands each plugin only the APIs its manifest declared:
  `artifact_path(name)` (confined under
  `<run_dir>/plugins/<plugin_name>/`, traversal + absolute paths
  rejected), `read_text(path)`, `env(name)`, and a
  `has_permission(perm)` check. Overreach raises
  `PluginPermissionError` (`E-PLG-002`, exit 7).

- **Subprocess sandbox** — `engine.plugins.sandbox.run_in_sandbox(...)`
  launches a child `python -m engine.plugins.sandbox_worker` with a
  filtered env (only `ALWAYS_INHERITED_ENV` + `SENTINEL_`/`SENTINELQA_`
  prefixes + declared `env.read:<NAME>` vars). Communication is one
  line of JSON in / one line of JSON out. Default 60s timeout
  surfaces as `ok=False` rather than crashing the host. Required
  permission is `subprocess.spawn`.

- **Versioning** — `is_compatible(requires_protocol, host)` reuses
  `packaging.specifiers.SpecifierSet`; bumping
  `PROTOCOL_VERSION` major requires a new ADR (CLAUDE.md §22, §40).
  Plugins declaring an incompatible range fail load with
  `PluginIncompatibleError` (`E-PLG-001`, exit 5).

- **CLI** — `sentinel plugins` Typer subapp with `list`, `info`, and
  `validate` subcommands. Exit codes: 0 success, 2 invalid usage /
  missing plugin / bad manifest, 7 internal error. JSON mode is
  available across all three.

- **Reference plugins** — two installable example packages under
  `examples/plugins/`: `sentinelqa-scanner-example` (HeaderChecker
  `ScannerPlugin`) and `sentinelqa-reporter-example` (CsvReporter
  `ReporterPlugin`). Both ship a `pyproject.toml` entry point, a
  README, and integration tests proving discovery + Protocol
  conformance.

- **Documentation** — `docs/dev/plugins.md` (how to write a plugin)
  and `docs/dev/plugin-permissions.md` (permission reference + path
  traversal guard + env-strip policy + drift checks).

The MVP delivers what PRD §22.2 promises: a third party can ship a
`pip install`-able package whose entry point loads into SentinelQA,
declares its capabilities and permissions, and is rejected at load
if it overreaches. Whether `discover()` is automatically wired into
`sentinel audit`'s module scheduler is a separate decision that any
future ADR will own — Phase 24 does not promise auto-scheduling.

---

## 23. Security and Threat Model

### 23.1 SentinelQA as a security-sensitive tool

SentinelQA itself handles:

- Test credentials.
- Cookies.
- App data.
- Network traces.
- Source code.
- Potential secrets.
- Vulnerability findings.

Therefore SentinelQA must implement:

- Secret redaction.
- Local-first storage.
- Encryption for cloud artifacts.
- Least-privilege tokens.
- Configurable retention.
- Audit logs.
- Safe target validation.
- No telemetry of sensitive artifacts by default.

### 23.2 Abuse prevention

The tool should reject unsafe scans when:

- Target is not allowlisted.
- Target is public production and destructive mode requested.
- User attempts stealth/evasion flags.
- Rate limits exceed safe defaults.
- Payload level is too aggressive for target mode.

---

## 24. MVP Definition

### 24.1 MVP goals

The MVP should prove that SentinelQA can:

1. Install easily.
2. Discover a local/staging web app.
3. Generate useful Playwright tests.
4. Run tests.
5. Perform basic a11y/performance/security checks.
6. Produce a quality score.
7. Output a professional HTML/JSON report.
8. Be callable from Python.
9. Be usable by an LLM agent through structured JSON.

### 24.2 MVP features

Required:

- CLI: `init`, `doctor`, `discover`, `plan`, `generate`, `audit`, `report`.
- TypeScript Playwright runner.
- Python SDK.
- Basic app crawler.
- Functional test generation.
- Axe-core accessibility scan.
- Basic performance budget.
- Security headers and cookie checks.
- LLM-code audit checks for dead buttons, missing routes, mock data, forms without submit.
- HTML report.
- JSON report.
- GitHub Actions template.

Not required:

- Cloud dashboard.
- Visual AI.
- Browser cloud integration.
- Full self-healing.
- Full security scanner.
- Mobile testing.

---

## 25. Engineering Milestones

### Phase 0: Technical spike

Duration: 1-2 weeks.

Deliverables:

- Minimal CLI.
- Playwright runner proof of concept.
- JSON report schema.
- Example Next.js app audit.

### Phase 1: MVP core

Duration: 4-6 weeks.

Deliverables:

- Config loader.
- Discovery crawler.
- Planner.
- Test generator.
- Runner.
- Basic analyzer.
- HTML/JSON report.

### Phase 2: CI and SDK

Duration: 3-4 weeks.

Deliverables:

- GitHub Action.
- Python SDK.
- JUnit/SARIF output.
- PR comment generator.
- Machine-readable agent responses.

### Phase 3: Advanced modules

Duration: 4-8 weeks.

Deliverables:

- Visual baseline testing.
- API testing.
- More security checks.
- Chaos tests.
- Flake detection.
- Safe test repair.

### Phase 4: Cloud beta

Duration: 8-12 weeks.

Deliverables:

- Hosted reports.
- Test history.
- Team projects.
- Quality trends.
- Artifact storage.
- Browser cloud integration.

---

## 26. Example Implementation Skeleton

### 26.1 CLI skeleton

```python
import typer
from sentinelqa.core import Sentinel

app = typer.Typer()

@app.command()
def audit(url: str, config: str = "sentinel.config.yaml"):
    qa = Sentinel.from_config(config)
    result = qa.audit(url=url)
    result.write_reports()
    raise typer.Exit(0 if result.passed else 1)

@app.command()
def generate(url: str, out: str = "tests/sentinel"):
    qa = Sentinel(project_path=".")
    plan = qa.plan(url=url)
    qa.generate_tests(plan=plan, out_dir=out)

if __name__ == "__main__":
    app()
```

### 26.2 Runner interface

```python
from abc import ABC, abstractmethod

class Runner(ABC):
    @abstractmethod
    def run(self, test_files: list[str]) -> "RunResult":
        pass
```

### 26.3 Module interface

```python
from abc import ABC, abstractmethod

class SentinelModule(ABC):
    name: str

    @abstractmethod
    def prepare(self, context):
        pass

    @abstractmethod
    def run(self, context):
        pass

    @abstractmethod
    def analyze(self, result):
        pass
```

---

## 27. Example Generated Playwright Test

```ts
import { test, expect } from "@playwright/test";

test.describe("Authentication", () => {
  test("user can log in with valid credentials", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel(/email/i).fill(process.env.TEST_USER_EMAIL!);
    await page.getByLabel(/password/i).fill(process.env.TEST_USER_PASSWORD!);
    await page.getByRole("button", { name: /sign in|log in/i }).click();

    await expect(page).toHaveURL(/dashboard|app|home/);
    await expect(page.getByRole("navigation")).toBeVisible();
  });

  test("login form shows validation for missing password", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel(/email/i).fill("test@example.com");
    await page.getByRole("button", { name: /sign in|log in/i }).click();

    await expect(page.getByText(/password.*required|required.*password/i)).toBeVisible();
  });
});
```

---

## 28. Differentiation Strategy

### 28.1 Do not claim

Do not claim:

- “First AI testing tool.”
- “First Playwright AI testing tool.”
- “Undetectable automation.”
- “Replaces all QA.”
- “Finds every bug.”

### 28.2 Claim

Claim:

- “Open-core agentic QA for LLM-built apps.”
- “Playwright-native release-confidence engine.”
- “CLI + Python SDK + MCP testing backend for coding agents.”
- “Full-stack quality gates for AI-generated software.”
- “Detects fake completeness in generated apps.”

### 28.3 Messaging

Tagline options:

1. **Prove your AI-generated app works.**
2. **The QA engine for LLM-built software.**
3. **Cursor writes. SentinelQA verifies.**
4. **Agentic testing for agentic development.**
5. **From generated code to verified release.**

---

## 29. Risks

### 29.1 Product risks

- Market already crowded.
- AI-generated tests may be flaky.
- Security scope could create liability.
- Developers may prefer raw Playwright.
- Enterprise buyers may prefer mature platforms.

### 29.2 Technical risks

- Discovery may miss flows behind auth.
- LLM planning may hallucinate tests.
- Generated tests may be brittle.
- Performance results may vary by environment.
- Visual diffs can produce noise.
- Security checks can generate false positives.

### 29.3 Mitigations

- Use deterministic execution and evidence.
- Human-review mode for risky changes.
- Confidence scores.
- Test stabilization loops.
- Clear safe-mode defaults.
- Plugin architecture for best-of-breed integrations.
- Start with narrow high-value workflows.

---

## 30. Success Metrics

### 30.1 Developer metrics

- Time to first audit under 5 minutes.
- Useful findings in first run.
- Generated test pass rate after stabilization above 80%.
- CLI install success above 95%.

### 30.2 QA metrics

- Regression defects caught before merge.
- Flake rate below 3%.
- Critical flow coverage above 80%.
- Mean time to diagnose failure reduced by 50%.

### 30.3 Business metrics

- Free-to-active conversion.
- Weekly test runs.
- CI integrations created.
- Reports shared.
- Team upgrades.

---

## 31. Open Questions

1. Should the MVP be Python-first CLI or Node-first CLI?
2. Should generated tests live in user repo by default or in `.sentinel/generated`?
3. Should cloud be delayed until open-source adoption exists?
4. Which LLM providers should be supported first?
5. Should the product use MCP from day one?
6. How much of the planner should be deterministic versus LLM-based?
7. Should SentinelQA provide its own visual diff engine or integrate with existing providers first?
8. Should the first target framework be Next.js only, or framework-agnostic from day one?

Recommended answers:

1. Python CLI + TS runtime.
2. User repo, with clear generated file markers.
3. Yes, delay cloud until CLI has traction.
4. Provider-agnostic through adapter interface.
5. Yes, at least basic MCP server.
6. Deterministic discovery, LLM planning, deterministic execution.
7. Basic built-in visual diff first, integrations later.
8. Framework-agnostic crawler, with first-class Next.js support.

### 31.1 Resolutions (Phase 27)

Every recommended answer above shipped as an Accepted ADR in Phase 27
and is enforced by the ADR-completeness guard
(`tests/integration/docs/test_adr_completeness.py`). The Phase 27
**Cloud boundary** trigger from CLAUDE.md §34 is also recorded.

| # | Question | Accepted ADR |
|---:|---|---|
| 1 | Python CLI vs Node CLI | [ADR-0034](docs/adr/0034-python-cli-typescript-runtime.md) |
| 2 | Generated tests location | [ADR-0035](docs/adr/0035-generated-tests-in-user-repo.md) |
| 3 | Cloud delay | [ADR-0036](docs/adr/0036-cloud-delayed-until-cli-traction.md) |
| 4 | LLM provider choice | [ADR-0037](docs/adr/0037-llm-provider-agnostic.md) |
| 5 | MCP from day one | [ADR-0038](docs/adr/0038-mcp-day-one.md) |
| 6 | Planner determinism vs LLM | [ADR-0039](docs/adr/0039-planner-deterministic-llm-split.md) |
| 7 | Visual diff: built-in vs integrate | [ADR-0040](docs/adr/0040-visual-built-in-first.md) |
| 8 | Framework targeting | [ADR-0041](docs/adr/0041-framework-agnostic-with-nextjs.md) |
| n/a | Cloud boundary (CLAUDE.md §34 trigger) | [ADR-0033](docs/adr/0033-cloud-boundary.md) |
| n/a | Docs site choice (Phase 27 deliverable) | [ADR-0032](docs/adr/0032-docs-site.md) |

---

## 32. Recommended Build Order

1. Config and CLI.
2. Playwright runtime wrapper.
3. Discovery crawler.
4. JSON report schema.
5. Functional test generator.
6. Runner and artifacts.
7. HTML report.
8. Accessibility module.
9. Security headers/cookie module.
10. Performance budget module.
11. Python SDK.
12. GitHub Action.
13. LLM/MCP interface.
14. LLM-code audit module.
15. Test repair module.
16. Visual/API/chaos modules.
17. Cloud dashboard.

---

## 33. Reference Sources

The following sources informed the competitive and market analysis. They should be re-checked before fundraising, public marketing, or legal claims.

1. Playwright homepage: https://playwright.dev/
2. Playwright Test Agents documentation: https://playwright.dev/docs/test-agents
3. QA Wolf homepage: https://www.qawolf.com/
4. QA Wolf AI testing tools article: https://www.qawolf.com/blog/the-12-best-ai-testing-tools-in-2026
5. mabl homepage: https://www.mabl.com/
6. mabl automated testing solutions article: https://www.mabl.com/blog/automated-testing-solutions
7. testRigor homepage: https://testrigor.com/
8. DevAssure homepage: https://www.devassure.io/
9. Autonoma vs QA Wolf: https://getautonoma.com/blog/autonoma-vs-qa-wolf
10. Autonoma open-source QA Wolf alternative: https://getautonoma.com/blog/opensource-alternative-qa-wolf
11. BrowserStack guide on AI and Playwright: https://www.browserstack.com/guide/modern-test-automation-with-ai-and-playwright
12. Sauce Labs AI automation testing comparison: https://saucelabs.com/resources/blog/comparing-the-best-ai-automation-testing-tools-in-2026
13. OWASP Web Security Testing Guide: https://owasp.org/www-project-web-security-testing-guide/
14. Shiplight AI testing tools comparison: https://www.shiplight.ai/blog/best-ai-testing-tools-2026
15. Functionize AI testing tools overview: https://www.functionize.com/automated-testing/ai-testing-tools

---

## 34. Final Verdict

The original idea is strong, but the market already has serious adjacent competitors. SentinelQA can still be a winning product if it avoids being a generic AI test generator and instead becomes the **agentic release-confidence engine for LLM-built applications**.

The most important differentiators are:

1. LLM-code-specific audits.
2. Open-core CLI and SDK.
3. Playwright-native test ownership.
4. Full-stack QA modules.
5. Safe adversarial testing.
6. MCP/LLM-native interface.
7. Evidence-based quality scoring.
8. CI/CD policy gates.

The product should be built as a serious developer infrastructure product, not a gimmick. The MVP should focus on local and CI value first, then expand into cloud analytics and enterprise workflows.

