# Changelog

All notable changes to SentinelQA are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). See
[`docs/dev/semver.md`](docs/dev/semver.md) for the full versioning policy.

## [Unreleased]

_No unreleased changes._

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
