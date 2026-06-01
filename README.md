<div align="center">
  <img src="./docs/assets/brand/wordmark.svg" alt="SentinelQA" width="540">

**Release-confidence for web apps. One score, one decision, on every push.**

[![CI](https://img.shields.io/github/actions/workflow/status/Ohswedd/sentinelqa/ci.yml?branch=main&label=ci)](https://github.com/Ohswedd/sentinelqa/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/badge/pypi-sentinelqa--cli-3776ab.svg)](https://pypi.org/project/sentinelqa-cli/)
[![npm](https://img.shields.io/badge/npm-%40sentinelqa%2Fts--runtime-cb3837.svg)](https://www.npmjs.com/package/@sentinelqa/ts-runtime)
[![Docker](https://img.shields.io/badge/docker-sentinelqa%2Frunner-2496ed.svg)](https://hub.docker.com/r/sentinelqa/runner)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)

</div>

SentinelQA crawls your app, generates Playwright tests, runs them, and turns
the result into one reproducible quality score with an explainable release
decision. It is built for **CI gates you can defend** and **agent loops you
can audit**.

![sentinel audit terminal demo](./docs/assets/demo-audit.svg)

## Why

| You want…                               | SentinelQA gives you…                                                                              |
| --------------------------------------- | -------------------------------------------------------------------------------------------------- |
| A defensible CI gate                    | One score per run, deterministic exit codes, explainable policy.                                   |
| Confidence in agent-generated code      | Dedicated checks for dead buttons, fake routes, mock data shipped, frontend-only auth.             |
| Security without a separate scanner     | Headers, cookies, CORS, CSRF, safe XSS / IDOR probes, secret scan, SBOM, OSV — all SARIF.          |
| Accessibility you can prove             | axe-core (WCAG 2.2 A / AA) + keyboard / focus / landmark checks; reports state what's automated.   |
| A safety boundary you don't have to add | Localhost-only by default. Public hosts blocked unless allowlisted. No stealth, no CAPTCHA bypass. |

## Install

Pick the surface that matches how you use it.

```bash
# Python CLI + SDK + MCP server (the main install)
uv pip install sentinelqa-cli # or: pip install sentinelqa-cli

# TypeScript runtime (for projects that drive Playwright themselves)
pnpm add -D @sentinelqa/ts-runtime # or: npm i -D @sentinelqa/ts-runtime

# Standalone Docker runner (CI without a Python install)
docker pull sentinelqa/runner:latest
```

`sentinelqa-cli` brings `sentinelqa-engine`, `sentinelqa-modules`,
`sentinelqa-integrations`, the Python SDK (`sentinelqa`), and the MCP server
(`sentinelqa-mcp`) transitively. Each package is independently installable
for embedded use.

## Run your first audit

```bash
sentinel init
sentinel doctor
sentinel audit --url http://localhost:3000
```

Open `.sentinel/runs/latest/report.html` for the rendered report, or
`.sentinel/runs/latest/findings.json` for the machine-readable form. Exit
codes are deterministic: `0` pass · `1` quality-gate fail · `2` config ·
`3` runtime · `4` unsafe target · `5` missing dependency · `6` test
execution · `7` internal.

## What's in the box

### Audit modules

| Module             | What it covers                                                                |
| ------------------ | ----------------------------------------------------------------------------- |
| **Functional**     | Login, signup, CRUD, role boundaries, file upload, payment sandbox.           |
| **Accessibility**  | axe-core (WCAG 2.2 A / AA), keyboard, focus, landmarks, accessible names.     |
| **Performance**    | Synthetic page / API / CPU / bundle / nav-stability budgets.                  |
| **Security**       | Headers, cookies, CORS, CSRF, safe XSS, IDOR smoke, secret scan, SARIF.       |
| **API**            | OpenAPI + GraphQL contracts, negative cases, auth matrix, latency budgets.    |
| **Visual**         | Pixel + perceptual diff, dynamic-content masking. No CI auto-accept.          |
| **Chaos**          | Slow network, offline, 500 / timeout mocking, session expiry edge cases.      |
| **LLM-code audit** | Dead buttons, fake routes, mock data shipped, frontend-only auth.             |
| **Supply chain**   | CycloneDX SBOM, OSV vulnerability lookup, license audit, postinstall scanner. |
| **Compliance**     | WCAG 2.2, GDPR baseline, CCPA baseline, SOC 2 audit-trail packs.              |

### Engine

Crawler · planner (deterministic + optional LLM) · generator (Playwright
specs + page objects + fixtures) · runner (local / Docker, retry +
quarantine) · failure analyzer (root-cause categorization) · scoring ·
reporter (HTML / JSON / SARIF / JUnit / Markdown) · healer (locator-repair
proposals).

### Distribution surfaces

| Surface         | What it is                                                          | Install                                          |
| --------------- | ------------------------------------------------------------------- | ------------------------------------------------ |
| `sentinel`      | Typer-based CLI; 19 commands                                        | `pip install sentinelqa-cli`                     |
| `sentinelqa`    | Typed Python SDK (`Sentinel`, `AuditResult`, `Finding`, `TestPlan`) | `pip install sentinelqa`                         |
| `sentinel mcp`  | MCP server exposing 12 `sentinel.*` tools over JSON-RPC             | `pip install sentinelqa-mcp`                     |
| `sentinel-ts`   | TypeScript runtime (Playwright helpers, JSONL bridge)               | `pnpm add -D @sentinelqa/ts-runtime`             |
| Docker runner   | Standalone image with everything pre-installed                      | `docker pull sentinelqa/runner:latest`           |
| GitHub Action   | Composite action + reusable workflow                                | [`integrations/github/`](./integrations/github/) |
| GitLab template | Drop-in CI template                                                 | [`integrations/gitlab/`](./integrations/gitlab/) |

## How to use it

```python
# Python SDK
from sentinelqa import Sentinel

result = Sentinel.audit("http://localhost:3000")
print(result.score, result.decision)
for finding in result.findings.critical:
    print(finding.title, finding.recommendation)
```

```yaml
# GitHub Actions
- uses: Ohswedd/sentinelqa@v1
  with:
    url: http://localhost:3000
    fail-under: 80
```

```bash
# MCP — point any MCP-capable agent at the stdio server
sentinel mcp
# Exposes: sentinel.audit, sentinel.findings, sentinel.suggest_fix,
# sentinel.verify_fix, sentinel.read_report, sentinel.discover, and more.
```

See the [SDK reference](./packages/python-sdk/README.md),
[MCP reference](./packages/mcp-server/README.md), and
[CI integration guide](./integrations/github/README.md) for details.

### Extending SentinelQA

Implement a `ScannerPlugin`, `RunnerPlugin`, or `ReporterPlugin`, register
the entry point, declare its capabilities. The plugin loader handles
discovery, permission gating, and a sandboxed subprocess worker. See
[`docs/dev/plugins.md`](./docs/dev/plugins.md).

## Documentation

- **Docs site** — <https://docs.sentinelqa.dev>
- [Architecture](./apps/docs/src/content/docs/concepts/architecture.md)
- [Module catalog](./apps/docs/src/content/docs/modules/index.md)
- [Error codes](./docs/user/error-codes.md)
- [Architecture Decision Records](./docs/adr/)

## Safety boundary

SentinelQA is for **authorized testing only**. By default it refuses any
target outside `localhost` / `127.0.0.1` / `::1`. Public hosts are blocked
unless explicitly added to your `target_allowlist`; security checks that
issue write-shaped requests additionally require proof-of-authorization.

We do not — and will not — ship: bot-detection / CAPTCHA bypass, stealth
automation, fingerprint evasion, credential stuffing, or unauthorized
exploitation. Read [SECURITY.md](./SECURITY.md) before pointing SentinelQA
at anything you do not own or are not explicitly authorized to test.

## Contributing

Pull requests welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the
fork-and-PR flow, Conventional Commits, and the Definition of Done. By
participating you agree to the
[Contributor Covenant Code of Conduct](./.github/CODE_OF_CONDUCT.md).

For security issues, follow the disclosure path in
[SECURITY.md](./SECURITY.md) — do not open a public issue.

## License

Apache-2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
