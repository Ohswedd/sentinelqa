# SentinelQA

[![CI](https://img.shields.io/github/actions/workflow/status/Ohswedd/sentinelqa/ci.yml?branch=main&label=ci)](https://github.com/Ohswedd/sentinelqa/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776ab.svg)](./apps/cli/pyproject.toml)
[![Node](https://img.shields.io/badge/node-%E2%89%A520-339933.svg)](./packages/ts-runtime/package.json)
[![Version](https://img.shields.io/badge/version-0.7.0-informational.svg)](./CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-pre--1.0-orange.svg)](./plans/STATUS.md)

> **Can this software be trusted enough to ship?**

SentinelQA is a Playwright-native release-confidence engine for
LLM-built and human-built software. It crawls your app, generates
Playwright tests, runs them locally or in Docker, categorizes failures
with root-cause hypotheses, and turns the result into one reproducible
score plus an explainable release decision — backed by evidence on
disk, not opinions.

It is designed for two audiences:

- Human engineers who need a defensible quality bar in CI.
- AI coding agents that need an evidence-grounded loop to ship safely.

> **Safety boundary.** SentinelQA is for **authorized testing only**.
> No stealth, no CAPTCHA bypass, no fingerprint evasion, no
> unauthorized targets, no destructive defaults. See `CLAUDE.md` §6,
> `PRD.md` §2, and [`SECURITY.md`](./SECURITY.md).

## Quickstart

```bash
uv pip install sentinelqa-cli
sentinel init
sentinel audit --url http://localhost:3000
```

The `audit` command runs the canonical 17-step run lifecycle: enforce
the safety policy, discover the app, plan and generate tests, run
them, analyze failures, score the result, and write versioned reports
to `.sentinel/runs/<run-id>/`. Exit codes are deterministic
(0 pass / 1 quality-gate fail / 2 config / 3 runtime / 4 unsafe
target / 5 missing dependency / 6 test execution / 7 internal). See
[`docs/user/error-codes.md`](./docs/user/error-codes.md).

![SentinelQA terminal demo — sentinel audit](./docs/assets/demo-audit.svg)

## What it does today

| Layer   | Module               | What it does                                                                                               |
| ------- | -------------------- | ---------------------------------------------------------------------------------------------------------- |
| Engine  | **Discovery**        | HTTP + Playwright crawl: routes, forms, APIs, auth boundaries, OpenAPI/GraphQL ingest.                     |
| Engine  | **Planner**          | Deterministic-first test plan generator with optional LLM proposals (provider-agnostic, budgeted).         |
| Engine  | **Generator**        | Playwright spec / page-object / fixture generator with semantic locators.                                  |
| Engine  | **Runner**           | Local and Docker Playwright runners, retry + quarantine, deterministic sharding.                           |
| Engine  | **Analyzer**         | Failure categorization (app vs test vs env vs flake), root-cause hypothesis, repro spec, retry decision.   |
| Module  | **Functional**       | Login / signup / CRUD / role / admin / file-upload / payment-sandbox coverage.                             |
| Module  | **Accessibility**    | axe-core (`wcag22a` / `wcag22aa`) + keyboard / focus / landmark / accessible-name checks.                  |
| Module  | **Performance**      | Synthetic page / API / CPU / bundle / nav-stability budgets — labeled synthetic, not RUM.                  |
| Module  | **Security (safe)**  | Headers, cookies, CORS, CSRF, safe XSS probe, IDOR smoke, secret scan, SARIF export, target allowlist.     |
| Module  | **API**              | OpenAPI / GraphQL contract validation, negative cases, auth, latency budgets.                              |
| Module  | **Visual**           | Baselines, diff threshold, dynamic-content masking. No CI auto-accept.                                     |
| Module  | **Chaos**            | Slow network, offline, 500/timeout mocking, session expiry, navigation edge cases.                         |
| Module  | **LLM-code audit**   | Dead buttons, fake routes, mock data shipped, frontend-only auth, missing CRUD edges.                      |
| Module  | **Supply chain**     | CycloneDX SBOM, OSV lookup, freshness, postinstall scan, license audit.                                    |
| Module  | **Compliance packs** | WCAG 2.2 / GDPR-baseline / CCPA-baseline / SOC 2 audit-trail. Automated checks only.                       |
| Surface | **Python SDK**       | `Sentinel`, `AuditResult`, `Finding`, `TestPlan`. Typed, stable, snapshot-tested.                          |
| Surface | **MCP server**       | Twelve `sentinel.*` tools for agent integration.                                                           |
| Surface | **CI**               | GitHub Actions + GitLab CI templates; PR comment poster; fast / standard / full / nightly / release modes. |

All findings carry evidence (artifact paths, redacted snippets, run
ids) and a safe-remediation note. The quality score is reproducible
from the persisted findings + module weights + gates.

## Documentation

- **Docs site** — [docs.sentinelqa.dev](https://docs.sentinelqa.dev)
  (DNS provisioned by owner; build deploys on every `main` push via
  [`.github/workflows/docs-deploy.yml`](./.github/workflows/docs-deploy.yml)).
- [`PRD.md`](./PRD.md) — product source of truth.
- [`CLAUDE.md`](./CLAUDE.md) — engineering constitution.
- [`plans/README.md`](./plans/README.md) — 37-phase execution plan
  (Phases 00–29 = MVP, Phases 30–36 = ecosystem expansion + v1.0.0
  release).
- [`plans/STATUS.md`](./plans/STATUS.md) — live phase status + gate
  reviews.
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). PRs against `main` use the
standard fork-and-PR flow. Conventional Commits are required
(`commitlint` runs in CI). AI tools may write code, but they are never
listed as Git authors, co-authors, owners, or maintainers
(`CLAUDE.md` §3).

If you found a security issue, **do not open a public issue**.
Follow the disclosure path in [`SECURITY.md`](./SECURITY.md).

## Status

Pre-1.0. The MVP (Phases 00–29) is on `main` and the working version
is `0.7.0`; the `v0.7.0` git tag is minted via the
[`pre-1.0 review`](./docs/release/pre-1.0-review.md) checklist. The
road to `v1.0.0` runs through Phases 30–36 (multi-provider LLM
adapters, browser-authenticated audits, extended security skills,
supply-chain audit, compliance packs, public release engineering,
ecosystem publish). See [`docs/dev/semver.md`](./docs/dev/semver.md)
for the tag plan.

Until `v1.0.0`, breaking changes are documented in
[`CHANGELOG.md`](./CHANGELOG.md) with a migration path
([`docs/dev/semver.md`](./docs/dev/semver.md) pre-1.0 rule §2).

## License

Apache-2.0 — see [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE) for
third-party attributions.
