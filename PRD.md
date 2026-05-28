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

- Mobile Appium support.
- Desktop Electron testing.
- Hosted browser execution cloud.
- Visual AI model.
- Compliance packs.
- Test data management UI.
- Human-in-the-loop QA marketplace.

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
  tests/
    unit/
    integration/
    e2e/
```

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

| Command            | Purpose                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------- |
| `--help` / `-h`    | Print the usage block.                                                                       |
| `--version` / `-V` | Print `@sentinelqa/ts-runtime <semver>`.                                                     |
| `run`              | `--input <run-config.json>` invokes Playwright with the custom reporter and streams JSONL.   |
| `list-tests`       | `--pattern <glob>` lists spec files; skips `node_modules` / `dist` / `.git` in every result. |
| `validate-helpers` | Sanity-check that the package loads, the redaction ruleset is readable, and helpers export.  |

Deterministic exit codes: `0` all pass, `1` ≥1 test failed/timed out, `2` Playwright crashed / config invalid / spawn failed / unknown command or flag, `7` programmer error (sync dispatch hit an async command). These map onto PRD §13.2 / CLAUDE §13.

### 15.4 JSONL event protocol

The runtime emits one JSON event per stdout line, parsed by Python's `engine/orchestrator/ts_bridge.py`. Every event carries the envelope `{type, schema_version, seq, ts}`; the discriminator is `type` and the schema covers fourteen kinds: `run.start`, `run.end`, `test.start`, `test.end`, `step.start`, `step.end`, `evidence`, `network.request`, `network.response`, `console`, `dom.snapshot`, `module.event`, `log`, `error`. The wire format is locked by `packages/shared-schema/ts-events.schema.json` (Draft 2020-12). A canonical fixture (`tests/golden/ts-events/sample.jsonl`) drives the cross-language parity tests; schema bumps require a successor ADR (ADR-0009 owns the rules).

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
  strategy: test_user
  login_url: /login
  username_env: TEST_USER_EMAIL
  password_env: TEST_USER_PASSWORD

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

---

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

