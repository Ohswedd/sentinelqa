# ADR-0034: Python-first CLI with a TypeScript Playwright runtime

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #1 asked whether the release should be a Python-first
CLI or a Node-first CLI. The the documentation's recommended answer was Python CLI +
TS runtime, and have shipped to that decision —
every command (`sentinel discover/plan/generate/test/audit/…`), the
SDK, the MCP server, the orchestrator, the scoring engine, and the
report dispatcher are Python; Playwright execution, browser
instrumentation, and the locator audit run in TypeScript via the
`@sentinelqa/ts-runtime` package.

This ADR is one of the eight Phase-27 open-question ADRs
required by

## Decision

**The CLI is Python; the Playwright runtime is TypeScript.** Python
owns CLI, SDK, orchestration, config, policy enforcement, module
registry, scoring, reports, agent-facing operations, and CI behavior
. TypeScript owns Playwright execution, browser
automation, locator utilities, runtime tracing, screenshot / video /
trace capture, and browser-side instrumentation. Python ↔ TypeScript
communication is explicit NDJSON-framed JSONL on stdout (ADR-0009).

## Consequences

- **Positive:** plays to each runtime's strengths — Python for typed domain models, Pydantic-validated config, MCP / agent surfaces; TypeScript for Playwright's first-class API.
- **Positive:** the data scientist / DevOps audience SentinelQA targets already has Python tooling; the CLI fits an `uv` / pip workflow.
- **Negative / trade-off:** every audit needs both runtimes installed (and a Chromium download). The doctor command surfaces missing Node / pnpm / `sentinel-ts` as exit-5 dependency errors so users see the missing piece immediately.
- **Negative / trade-off:** two test suites, two CI lanes, two lint toolchains. Mitigated by `make ci` running both end-to-end and by the parity tests for the JSONL protocol (`PROTOCOL_VERSION` cross-checked in `tests/integration/runtime/`).
- **Follow-up obligations:** keep the protocol versioned (ADR-0009); reject any "shadow runtime" — Python must not start spawning headless browsers directly, and TypeScript must not start owning policy or scoring.

## Alternatives considered

- **Node-first CLI.** Rejected — Pydantic-style config validation, the MCP server, the Healer, and the scoring engine are all naturally Python. A Node CLI would force half of the codebase into a runtime with weaker static typing for our typed domain layer.
- **Pure-Python Playwright (via the `playwright` Python package).** Rejected — Playwright's TypeScript API is the supported surface and the reporter / locator-strategy story is richer there. Re-implementing the locator audit in Python would duplicate code without benefit.

## References

- our product spec Open Question #1 + recommended answer
- our product spec TS Runtime
- our engineering rules
- Related ADRs: ADR-0002 (Language strategy), ADR-0009 (Python↔TS protocol)
