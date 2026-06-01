# Changelog

All notable changes to SentinelQA are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). See
[`docs/dev/semver.md`](docs/dev/semver.md) for the full versioning policy.

## [Unreleased]

_No unreleased changes._

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
