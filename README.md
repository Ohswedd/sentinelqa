<div align="center">

# SentinelQA

**A Playwright-native release-confidence engine for LLM-built and human-built web apps.**

[![CI](https://img.shields.io/github/actions/workflow/status/Ohswedd/sentinelqa/ci.yml?branch=main&label=ci)](https://github.com/Ohswedd/sentinelqa/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776ab.svg)](./apps/cli/pyproject.toml)
[![Node](https://img.shields.io/badge/node-%E2%89%A520-339933.svg)](./packages/ts-runtime/package.json)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](./CHANGELOG.md)

</div>

SentinelQA crawls your app, generates Playwright tests, runs them locally or in
Docker, categorizes failures with root-cause hypotheses, and turns the result
into one reproducible quality score with an explainable release decision —
backed by evidence on disk, not opinions.

It is built for **CI gates you can defend** and **agent loops you can audit**.

![SentinelQA terminal demo — sentinel audit](./docs/assets/demo-audit.svg)

---

## Why SentinelQA

- **Release confidence, not just tests.** One quality score per run, derived
  from N modules and a transparent scoring policy, with deterministic exit
  codes you can gate CI on.
- **Built for AI-generated apps.** Dedicated checks for dead buttons, fake
  routes, mock data shipped to production, missing CRUD edges, frontend-only
  auth, and hardcoded credentials in bundles.
- **Safety boundary, by design.** Authorized targets only. No stealth, no
  CAPTCHA bypass, no fingerprint evasion. Public hosts are blocked unless
  explicitly allowlisted.
- **Python CLI + TypeScript runtime.** Python orchestrates and grades;
  Playwright executes. Drive it from a shell, the Python SDK, or any
  MCP-capable agent.

---

## Quick start

```bash
uv pip install sentinelqa-cli
sentinel init
sentinel audit --url http://localhost:3000
```

Open `.sentinel/runs/latest/report.html` for the rendered report, or
`.sentinel/runs/latest/findings.json` if you want the machine-readable form.

Exit codes are deterministic — `0` pass, `1` quality-gate fail, `2` config,
`3` runtime, `4` unsafe target blocked, `5` missing dependency, `6` test
execution, `7` internal. See [`docs/user/error-codes.md`](./docs/user/error-codes.md).

---

## What's in the box

| Layer   | Module              | What it does                                                                                         |
| ------- | ------------------- | ---------------------------------------------------------------------------------------------------- |
| Engine  | **Discovery**       | HTTP + Playwright crawl: routes, forms, APIs, auth boundaries, OpenAPI/GraphQL ingest.               |
| Engine  | **Planner**         | Deterministic-first test plan generator with optional LLM proposals (provider-agnostic, budgeted).   |
| Engine  | **Generator**       | Playwright spec / page-object / fixture generator with semantic locators.                            |
| Engine  | **Runner**          | Local and Docker Playwright runners, retry + quarantine, deterministic sharding.                     |
| Engine  | **Analyzer**        | Failure categorization (app vs test vs env vs flake), root-cause hypothesis, repro spec.             |
| Engine  | **Scoring**         | Reproducible quality score with severity penalties and policy gates.                                 |
| Engine  | **Reporter**        | `run.json`, `findings.json`, `score.json`, JUnit XML, SARIF, HTML, Markdown — all schema-versioned.  |
| Engine  | **Healer**          | Locator repair proposals with confidence tiers. Human review for risky changes.                      |
| Module  | **Functional**      | Login / signup / CRUD / role / admin / file-upload / payment-sandbox coverage.                       |
| Module  | **Accessibility**   | axe-core (WCAG 2.2 A / AA) + keyboard / focus / landmark / accessible-name checks.                   |
| Module  | **Performance**     | Synthetic page / API / CPU / bundle / nav-stability budgets — labeled synthetic, not RUM.            |
| Module  | **Security (safe)** | Headers, cookies, CORS, CSRF, safe XSS probe, IDOR smoke, secret scan, SARIF export.                 |
| Module  | **API**             | OpenAPI / GraphQL contract validation, negative cases, auth, latency budgets.                        |
| Module  | **Visual**          | Pixel + perceptual diff, dynamic-content masking. Baselines never auto-accepted in CI.               |
| Module  | **Chaos**           | Slow network, offline, 500 / timeout mocking, session expiry, navigation edge cases.                 |
| Module  | **LLM-code audit**  | Dead buttons, fake routes, mock data shipped, frontend-only auth, missing CRUD edges.                |
| Module  | **Supply chain**    | CycloneDX SBOM, OSV vulnerability lookup, freshness, postinstall scan, license audit.                |
| Module  | **Compliance**      | WCAG 2.2 / GDPR-baseline / CCPA-baseline / SOC 2 audit-trail packs. Automated checks only.           |
| Surface | **Python SDK**      | `Sentinel`, `AuditResult`, `Finding`, `TestPlan`. Typed and snapshot-tested.                         |
| Surface | **MCP server**      | Twelve `sentinel.*` tools for agent integration over JSON-RPC / NDJSON.                              |
| Surface | **CI integration**  | GitHub Actions + GitLab CI templates; PR comment poster; fast / standard / full / nightly / release. |

Every finding carries reproducible evidence (artifact paths, redacted
snippets, run IDs) and a safe-remediation note. The quality score is
derivable from the persisted findings, module weights, and policy gates.

---

## Documentation

- **Docs site** — [docs.sentinelqa.dev](https://docs.sentinelqa.dev)
- [Architecture overview](./docs/dev/local-setup.md)
- [Module reference](./apps/docs/src/content/docs/modules/index.md)
- [Python SDK](./packages/python-sdk/README.md)
- [MCP server](./packages/mcp-server/README.md)
- [CI integration](./integrations/github/README.md)
- [Architecture Decision Records](./docs/adr/)
- [Error codes](./docs/user/error-codes.md)

---

## Safety boundary

SentinelQA is for **authorized testing only**. By default it refuses any
target outside `localhost` / `127.0.0.1` / `::1`. Public hosts are blocked
unless explicitly added to your `target_allowlist`, and security checks that
issue write-shaped requests additionally require proof-of-authorization.

We do not — and will not — ship:

- Bot-detection or CAPTCHA bypass.
- Stealth automation or fingerprint evasion.
- Credential stuffing, spam automation, or platform manipulation.
- Unauthorized vulnerability exploitation.

Read [SECURITY.md](./SECURITY.md) before pointing SentinelQA at anything you
do not own or are not explicitly authorized to test.

---

## Contributing

Pull requests welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the
fork-and-PR flow, Conventional Commits, the Definition of Done, and how the
test matrix is structured.

For security issues, **do not open a public issue** — follow the disclosure
path in [SECURITY.md](./SECURITY.md).

By participating you agree to the
[Contributor Covenant Code of Conduct](./.github/CODE_OF_CONDUCT.md).

---

## License

Apache-2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE) for third-party
attributions.
