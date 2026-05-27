# SentinelQA

**SentinelQA** is a Playwright-native release-confidence engine for LLM-built and human-built software. It answers one question with evidence:

> Can this software be trusted enough to ship?

> **Safety boundary.** SentinelQA is for **authorized testing only**. No stealth, no evasion, no CAPTCHA bypass, no unauthorized targets, no destructive defaults. See `CLAUDE.md` §6 and `PRD.md` §2.

## Status

`Planned` — Phase 00 (foundation) in progress. No product behavior is shipped yet. See `plans/STATUS.md` for live state.

## Documents

- [`PRD.md`](./PRD.md) — product source of truth.
- [`CLAUDE.md`](./CLAUDE.md) — engineering constitution; mandatory operating rules.
- [`plans/README.md`](./plans/README.md) — 30-phase execution plan.
- [`plans/STATUS.md`](./plans/STATUS.md) — live status, active phase, gate-review log.
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records.
- [`docs/dev/`](./docs/dev/) — contributor docs.

If `CLAUDE.md` and `PRD.md` conflict, follow the authority order in `CLAUDE.md` §2 and update the docs before continuing.

## Languages

- **Python 3.11+** owns the CLI, SDK, orchestration, config, safety policy, modules, scoring, and reports (PRD §11.3, CLAUDE.md §8).
- **TypeScript / Node.js 20+** owns the Playwright runtime, browser automation, and runtime tracing (PRD §15, CLAUDE.md §8 + §21).

## Repository layout

The top-level folders mirror `PRD.md` §11.2. Each has its own `README.md`:

- [`apps/`](./apps/) — CLI, docs site, dashboard.
- [`packages/`](./packages/) — Python SDK, TS runtime, MCP server, shared schemas.
- [`engine/`](./engine/) — orchestrator, discovery, planner, generator, runner, analyzer, healer, reporter, policy.
- [`modules/`](./modules/) — functional, API, a11y, perf, visual, security, chaos, LLM-audit.
- [`integrations/`](./integrations/) — GitHub, GitLab, BrowserStack, Sauce Labs, Slack, Jira, Linear.
- [`examples/`](./examples/) — Next.js, FastAPI, Django, Flask, React-Vite reference apps.
- [`tests/`](./tests/) — cross-package unit, integration, e2e suites.
- [`docs/`](./docs/) — ADRs, contributor docs, user docs.

## Quick start (Phase 00 scope)

Full developer setup lands in task 00.09 (`CONTRIBUTING.md` + `docs/dev/local-setup.md`). For now: this repo is scaffolding only.

## License & ownership

License is captured in `LICENSE` (Phase 00.08). The repo stays **private** until the human owner decides otherwise (`CLAUDE.md` §3). No AI tool is listed as an owner, maintainer, or co-author — ever (`CLAUDE.md` §3).
