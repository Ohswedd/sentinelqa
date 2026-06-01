# Changelog

All notable changes to SentinelQA are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). See
[`docs/dev/semver.md`](docs/dev/semver.md) for the full versioning policy.

## [Unreleased]

_No unreleased changes._

## [1.5.0] - 2026-06-01

Integration-breadth release. Nine additions covering the CI surfaces,
notifier endpoints, metrics sinks, observability stack, and the
GitHub issue lifecycle teams have asked for since `1.0.0`.

### Added

CI templates (`integrations/`):

- **Bitbucket Pipelines** template (`bitbucket/bitbucket-pipelines.sentinel.yml`).
- **Azure DevOps Pipelines** template
  (`azure_devops/azure-pipelines.sentinel.yml`) with parameters
  for `url`, `mode`, `fail_under`, `version`, `python_version`,
  `node_version`.
- **CircleCI orb** (`circleci/orb.yml`) — `commands.install_sentinelqa`,
  `commands.run_audit`, `commands.publish_artifacts`, `jobs.audit`.
- **Jenkins shared library** (`jenkins/vars/sentinelAudit.groovy` +
  `jenkins/README.md`).

Notifiers (`integrations/`):

- **Microsoft Teams** notifier (`teams/`). Posts an Adaptive Card to
  an Incoming Webhook URL; dedup cache + secret redaction modelled
  on the Slack notifier.
- **Discord** notifier (`discord/`). Posts a coloured embed card with
  the score, status, and per-severity ladder.
- **PagerDuty** Events API V2 trigger (`pagerduty/`). Triggers an
  incident when `quality_score < threshold`; auto-resolves on the
  next-passing run via a stable per-host `dedup_key`. Severity
  ladders by gap (>30 → critical, >15 → error, >5 → warning).

Metrics sinks (`integrations/metrics/`):

- **Datadog** Metrics V2 push (`metrics/datadog.py`). Emits
  `sentinelqa.quality_score`, `sentinelqa.duration_ms`,
  `sentinelqa.findings.count` (per severity), and
  `sentinelqa.module.duration_ms`.
- **New Relic** Metric API push (`metrics/newrelic.py`).
- **Honeycomb** Events push (`metrics/honeycomb.py`). Flat-key
  events with `sentinelqa.*` namespace.

Observability:

- **OpenTelemetry** tracer wrapper (`integrations/otel/`). Opt-in
  via `SENTINELQA_OTEL_ENABLED=1`; OTLP/HTTP exporter is lazy-
  loaded so the dependency stays optional. Degrades cleanly to a
  no-op when the SDK is missing.

GitHub:

- **GitHub auto-issue lifecycle** (`integrations/github/issue_lifecycle.py`).
  Fingerprint-based dedup (sha256 over `module|category|code|title`);
  per-category issue templates (network-5xx, page-error, headers)
  with extra labels; `close_resolved_issues` walks current findings
  vs open issues and closes those whose fingerprint is no longer
  present, posting a resolution comment naming the closing run.

### Status

No wire schema change. The Python SDK API snapshot is unchanged.
The MCP wire protocol is unchanged. The OpenTelemetry SDK is an
optional dependency; activation is opt-in.

## [1.4.0] - 2026-06-01

LLM / Agent release. Eight additions that make the agent loop sharper
without breaching the deterministic-first contract.

### Added

- **Local-LLM defaults** (`engine/llm/defaults.py`). 5-step
  resolution chain: explicit caller → `SENTINELQA_LLM_PROVIDER` env
  → cloud API-key env vars (Anthropic / OpenAI / Gemini / Mistral /
  Groq / OpenRouter) → local Ollama TCP probe →
  `null`. `SENTINELQA_DISABLE_LOCAL_LLM=1` forces opt-out.
- **Vision LLM bridge** (`engine/llm/vision.py` +
  `vision_anthropic.py`). `VisionRequest` → `VisionAnalysis` with a
  locked system prompt asking for ONE sentence describing the
  screenshot; PNG / JPEG / WebP / GIF magic-byte sniffing; sentence
  sanitiser capping output at 280 characters. Anthropic Messages-API
  adapter ships; OpenAI / Gemini return `available=False` until
  their adapters land.
- **`sentinel ask "..."`** (`apps/cli/.../ask_cmd.py`). Read-only NL
  query over a completed run. Locked prompt template wraps the
  question as untrusted data, ships the run context as a bounded
  JSON block, falls back to a deterministic explainer when no LLM
  provider is available. JSON / quiet / human output modes.
- **MCP tool: `sentinel.compare_runs`** — diff two runs, return new
  / resolved / persistent findings, severity regressions /
  improvements, and the quality-score delta.
- **MCP tool: `sentinel.coverage_gaps`** — walk discovery.json +
  coverage.json and return uncovered routes / forms / API endpoints
  ranked by risk (1–5).
- **MCP tool: `sentinel.replay_with_change`** — apply a unified-diff
  patch to a materialised copy of the working tree, run the lifecycle
  on the patched tree, return the findings diff vs the source run.
- **LLM-generated remediation patches**
  (`engine/healer/patch_builder.py`). Builds a locked prompt asking
  for a unified-diff and runs a strict safety check that rejects:
  removed `expect(...)`, `assert ...`, or `page.waitFor*` calls;
  `test.skip` / `test.only` additions; bug-swallowing try/except;
  multi-file diffs; diffs over 60 lines; modifications to the test
  file itself.
- **`sentinel auth record` recorder primitives**
  (`engine/auth/recorder.py`). Codegen command builder + transcript
  parser + optional LLM post-condition suggester (selector /
  url_pattern / text_contains / cookie_present) + profile-YAML
  writer.

### Status

The `run.json` / `findings.json` / `score.json` / JUnit / SARIF wire
schemas are unchanged from `1.0.0`. The Python SDK API snapshot is
unchanged. The MCP wire protocol is unchanged; three new tools are
additive (`sentinel.compare_runs`, `sentinel.coverage_gaps`,
`sentinel.replay_with_change`).

## [1.3.0] - 2026-06-01

Module-gaps release. Thirteen additions covering the most common
holes a security-conscious team notices on day one: browser-side
forensics, deeper security/compliance scanning, realtime-transport
auditing, PII detection, image optimisation, i18n/RTL, and 2FA /
WebAuthn flow recording.

### Added

Browser runtime captures:

- **JavaScript / TypeScript error capture.** Every unhandled
  browser exception now produces a structured `page.error` event
  (TS runtime + Python parser + `Finding` converter). Includes
  error name, redacted message, redacted stack, and a best-effort
  source URL extracted from the stack.
- **5xx network forensics.** Every response in the 500–599 range
  during a test now produces a `network.failure` event with the
  redacted request + response headers and a bounded (2 KiB) body
  preview. Converted into a `network-5xx` `Finding` (CWE-755)
  with severity bumped when the corresponding test failed.

Security module:

- **Open-redirect deeper scan.** Enumerator finds every URL
  parameter from a curated 28-name list (`redirect`, `next`,
  `return_to`, ...); bypass-payload generator emits 13 canonical
  vectors (protocol-relative, `@`-injection, CRLF, IPv4 decimal,
  IPv6 loopback, double-URL-encoded, dot-bypass, ...); response
  evaluator strips userinfo before the allowlist check.
- **CSP / SRI / HSTS scoring.** Each header now returns a 0-100
  strictness score with reasons. CSP penalises `'unsafe-inline'`,
  wildcards, missing `default-src`/`frame-ancestors`/`object-src`.
  SRI scores the fraction of off-host scripts + stylesheets covered
  by an `integrity` attribute. HSTS applies the
  [hstspreload.org](https://hstspreload.org/) rules.
- **HTTP/2 + HTTP/3 negotiation probe.** Records ALPN, HTTP/2,
  HTTP/3, and `Alt-Svc` for the target; emits per-gap findings
  and a compact `A+`-style grade.
- **PII detection in response bodies.** Pattern matcher for SSN
  (area-sanity-checked), credit card (Luhn-verified), email,
  US phone, IPv4 (skips loopback), IBAN, ZIP+4. Every match is
  masked at output (`***-**-1234`) so PII never leaves the module.
- **Service-worker audit.** Detects registration + scope from the
  HTML; flags eager `Notification.requestPermission` calls (the
  most-disliked PWA anti-pattern) and `CacheFirst` strategies on
  sensitive endpoints (`/api/me`, `/auth/...`).

API module:

- **WebSocket + Server-Sent Events coverage.** Detection of
  `wss://` URLs and `new EventSource(...)` calls in HTML + JS
  bundles; evaluators for cross-origin handshakes (CSWSH),
  unauthenticated upgrades, unbounded message size; SSE checks
  for retry-storm intervals and `Last-Event-ID` handling.
- **GraphQL subscriptions.** Schema parser extracts every field on
  the `Subscription` type; auth evaluator flags missing
  `@auth`/`@requireAuth` directives; session evaluator catches
  anonymous handshakes, high message rates, uncapped payloads,
  and missing connection rate-limits.

Performance module:

- **Image / favicon optimisation.** HTML scanner flags heavy
  JPEG/PNG without WebP/AVIF fallback inside a `<picture>` ladder,
  missing `loading="lazy"` on below-fold images, and missing
  `width`/`height` attributes (CLS contributors). Optional alt-text
  audit overlaps with a11y.

Compliance module:

- **Cookie consent → behaviour parity.** Classifies cookies as
  `strictly_necessary` / `analytics` / `marketing` / `tracking` /
  `unknown` via a curated allowlist + 20+ regex patterns (Google
  Analytics, Facebook Pixel, Microsoft UET, Hotjar, ...). Diff
  between the initial cookie jar and the post-reject jar; any
  non-essential survivor becomes a `gdpr:Art.6` finding.

Functional module:

- **i18n / RTL audit.** Detects untranslated English UI strings on
  non-English renders (Sign in / Submit / Cancel / Continue / ...);
  enforces `<html dir="rtl">` for Arabic / Hebrew / Farsi / Urdu;
  flags `<html lang>` mismatches after a locale switch.

Auth subsystem:

- **2FA / WebAuthn flow recording.** Detects TOTP / WebAuthn /
  SMS / email-link MFA prompts from the login HTML. Computes
  RFC 6238 TOTP codes from a base32 secret. Emits a declarative
  `WebAuthnVirtualAuthenticator` spec the runner converts into a
  Chrome DevTools virtual authenticator (no physical key needed
  in CI). Small DSL (`build_totp_script`, `build_webauthn_script`)
  feeds the runner.

### Status

The `run.json` / `findings.json` / `score.json` / JUnit / SARIF
wire schemas are unchanged from `1.0.0`. Two new JSONL event types
(`page.error`, `network.failure`) flow over the TS↔Python bridge;
they're additive (`schema_version` on existing events is unchanged).
The Python SDK API surface is unchanged. The MCP wire protocol is
unchanged.

## [1.2.0] - 2026-06-01

Test-economics release. Six additions that make audits cheap to run
often: a content-addressed cache for discovery + plan, diff-aware
test selection, fingerprint-based `--since` short-circuiting,
bounded parallel module execution, and a cross-run flake database.

### Added

- **Source fingerprint + cache store.** New
  `engine.cache` package: `SourceFingerprint` (deterministic sha256
  over the source surface, ignoring node_modules / .venv / build
  trees) and `CacheStore` (atomic, namespaced, disk-backed byte
  store under `.sentinel/cache/`). Foundation for the rest of this
  release.
- **Discovery cache.** `sentinel audit` now consults
  `cache.discovery` keyed on the source fingerprint at the start
  of `discover_app`. If a prior run produced `discovery.json`
  with the same fingerprint, the bytes are restored before any
  discovery hook runs.
- **Plan cache.** `plan.json` is keyed on
  `(fingerprint, requested_modules)` so the planner skips
  recomputation when nothing source-relevant changed. Dry-run plans
  are intentionally not cached.
- **`sentinel audit --changed-only` (smart test selection).**
  Reads `git diff <base>...HEAD` plus unstaged + untracked file
  lists, maps each path to the audit modules it impacts, and
  restricts the run to that subset. `--diff-base` defaults to
  `origin/main`. No-op exit when only docs / unrelated files
  changed. Lockfiles / Dockerfiles / framework configs invalidate
  every module.
- **`sentinel audit --since <run-id|latest>`.** Short-circuits the
  entire audit when the current source fingerprint matches the prior
  run's. Exits 0 with status `unchanged` — no run created, no
  cache.json overwritten. Useful in CI as a poor-man's "is anything
  in scope?" gate.
- **`sentinel audit --parallel-modules N`** (1..16). Bounded
  `ThreadPoolExecutor`-based module execution. Safety policy still
  enforces before discovery, so no module touches the network ahead
  of the policy. Worker results are merged back in canonical input
  order — the artifact tree is byte-identical to the sequential path.
- **Cross-run flake DB + `sentinel flake` CLI.** New sqlite-backed
  database at `.sentinel/flake.db` (runs table + outcomes table)
  populated automatically by the lifecycle at the end of every
  audit. `sentinel flake list` prints the top-N flakiest
  `(module, test_id)` pairs honouring a min-runs floor;
  `sentinel flake stats` prints totals. Writes are best-effort —
  a DB failure never breaks the run.

### Changed

- New additive artifact `cache.json` under each run directory
  recording the source fingerprint, discovery cache hit/miss, and
  plan cache hit/miss. The wire schema of `run.json` is unchanged.
- The lifecycle's cache root now defaults to a sibling of the
  artifacts root (`<runs>/../cache`) rather than CWD, so tests
  using a tmp_path artifacts root get an isolated cache automatically.

### Status

The `run.json` / `findings.json` / `score.json` / JUnit / SARIF
wire schemas are unchanged from `1.0.0`. The Python SDK public
surface, the MCP wire protocol, and the exit-code table are
unchanged. Existing callers see no behavioural change unless they opt
into one of the new flags or read the new `cache.json` artifact.

## [1.1.0] - 2026-06-02

Developer-experience release. Seven additions that close the gap between
"installed" and "first useful audit", without changing any persisted
schema, exit code, or scoring math.

### Added

- **Interactive `sentinel init` wizard.** Five Rich-styled prompts —
  project name, base URL, auth strategy, eight module booleans, confirm
  — each defaulted from project detection (package.json /
  pyproject.toml / lockfiles). Five Enter presses produce a working
  `sentinel.config.yaml`. `--non-interactive`, `--json`, and `--quiet`
  bypass the wizard and use the detection-only renderer that shipped in
  `1.0.0`, so CI invocations are unchanged.
- **`sentinel audit --watch`.** A stdlib-only file-watch loop re-runs
  the audit on file changes during local development. Refuses to start
  in CI mode. New `--watch-root <path>` lets the user point the
  watcher at a sub-directory.
- **`sentinel migrate`.** Adapts an existing Cypress or Playwright
  test suite into SentinelQA-tagged adapter specs under
  `tests/sentinel/migrated/`. Conservative by design — never rewrites
  assertions or selectors. Honors `--dry-run`, `--force`,
  `--framework`, `--path`. Writes `.sentinel/migrate/manifest.json` so
  re-runs are idempotent.
- **VS Code extension.** New TypeScript workspace at
  `apps/vscode-extension/` (`Ohswedd.sentinelqa-vscode`). Findings
  tree view grouped by severity, jump-to-source on `code_ref`, inline
  "Apply fix" command wrapping `sentinel fix --apply`,
  refresh / run-audit toolbar buttons. Two settings:
  `sentinelqa.projectRoot` and `sentinelqa.cliCommand`.
- **Browser extension.** New Manifest V3 workspace at
  `apps/browser-extension/` ("SentinelQA — Audit this page"). Posts
  the active tab's URL to a local `sentinel mcp --http` server on
  loopback (`127.0.0.1` / `localhost` / `::1` only); a hardened
  validator (`src/loopback.ts` + 8 vitest cases) refuses public
  hosts, `localhost.attacker.example`-style impersonation, non-http
  schemes, and out-of-range ports.
- **Shell completion advertised in `--help`.** `sentinel` now ships
  with `add_completion=True`, exposing the standard Typer
  `--install-completion` / `--show-completion` surface (bash, zsh,
  fish, powershell). New doc page `docs/user/shell-completion.md`
  walks through install per shell.
- **Onboarding doctor diagnostics with OS-aware install hints.**
  Every `sentinel doctor` dependency failure now appends a
  copy-pasteable install command tailored to the user's OS
  (Homebrew on macOS, NodeSource on Debian/Ubuntu, dnf on Fedora,
  pacman on Arch, winget on Windows). New
  `apps/cli/src/sentinel_cli/platform_install_hints.py` carries the
  catalogue for Python / Node / Playwright / Docker / httpx across
  six platforms.

### Changed

- `sentinel --help` lists the new `migrate` command, advertises
  `--install-completion`, and carries a one-line completion hint in
  the root help string.
- `sentinel doctor` suggestions are longer (now include the install
  hint suffix). JSON-mode output is unchanged structurally.

### Status

All schemas (`run.json`, `findings.json`, `score.json`, JUnit, SARIF,
agent envelope) are unchanged from `1.0.0`. Exit codes are unchanged.
The Python SDK public surface is unchanged. The MCP wire protocol is
unchanged. This release is a strict superset of `1.0.0` for callers
that don't opt into the new commands.

## [1.0.0] - 2026-06-01

First public release.

### Added

- **CLI** — `sentinel` Typer-based command suite covering `init`, `doctor`,
  `discover`, `plan`, `generate`, `test`, `audit`, `functional`, `a11y`,
  `perf`, `security`, `api`, `visual`, `chaos`, `llm-audit`, `fix`, `ci`,
  `report`, `plugins`, and `mcp`. Deterministic exit codes; JSON and human
  output modes; CI-safe behaviour.
- **Engine** — domain models, strict config loader, safety policy, typed
  error hierarchy, run lifecycle, scoring, reporter pipeline (HTML / JSON /
  SARIF / JUnit / Markdown), analyzer (failure categorization), planner
  (deterministic-first + optional LLM), healer (locator repair proposals).
- **Modules** — functional, accessibility (WCAG 2.2 A / AA via axe-core),
  performance (synthetic budgets), security (safe defensive checks with
  SARIF export), API (OpenAPI / GraphQL contract + negative cases), visual
  (pixel + perceptual diff), chaos (bounded scenarios), LLM-code audit
  (dead buttons, fake routes, mock data shipped, frontend-only auth),
  supply-chain (CycloneDX SBOM, OSV lookup, license audit, postinstall
  scanner), compliance packs (WCAG 2.2, GDPR baseline, CCPA baseline,
  SOC 2 audit-trail).
- **Surfaces** — Python SDK (`sentinelqa`) with stable public API and
  snapshot test; MCP server (`sentinelqa-mcp`) exposing twelve
  `sentinel.*` tools over JSON-RPC; TypeScript runtime
  (`@sentinelqa/ts-runtime`) with Playwright helpers, JSONL bridge, and
  the `sentinel-ts` CLI.
- **Integrations** — GitHub Actions composite action + reusable workflow,
  GitLab CI template, PR / MR comment posters, Slack / Jira / Linear
  adapters, BrowserStack + Sauce Labs runner plugins.
- **Auth** — encrypted Playwright `storage_state` vault with OS-keyring
  master key; `sentinel auth login` interactive flow; OAuth + LLM-web
  profile recipes.
- **LLM providers** — provider-agnostic adapter layer covering Anthropic,
  OpenAI, Gemini, Ollama, Azure OpenAI, Vertex AI (RS256 JWT), Mistral,
  Groq, OpenRouter; shared budget / rate-limit / redaction plumbing.
- **Plugins** — entry-point-discovered scanner / runner / reporter
  plugins with declared capabilities and a sandboxed subprocess worker.
- **Release engineering** — `make build-all`, `make inspect-all`,
  `make audit-metadata`, `make audit-license-headers`,
  `make changelog-draft`, build / inspect scripts, and the four publish
  workflows (PyPI Trusted Publisher, npm with provenance, Docker Hub
  multi-arch with SBOM + provenance, GitHub Release).
- **Public-release surface** — README, contributor guide, Code of
  Conduct (Contributor Covenant 2.1), Security Policy with 90-day
  coordinated disclosure, structured GitHub issue forms, Dependabot
  configuration, branch-protection documentation, docs site
  (`docs.sentinelqa.dev`).

### Status

`v1.0.0` is the first publication-eligible tag. Publishing is driven by
[`docs/release/publish-runbook.md`](docs/release/publish-runbook.md).
