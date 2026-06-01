# ADR-0002: Language strategy (Python + TypeScript)

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

SentinelQA must run real browsers (Playwright is the canonical option, JavaScript-first) AND expose an SDK + agent interface that data scientists, security engineers, and LLM coding agents can adopt without learning a new ecosystem (Python is the dominant language in those communities). A single-runtime approach forces one constituency to suffer. the documentation and §8.3 split the system: Python owns the orchestrator, CLI, SDK, and modules; TypeScript owns Playwright execution and runtime helpers.

## Decision

Adopt the two-runtime split exactly as the documentation prescribes:

| Runtime                   | Owns                                                                                                                                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python 3.11+**          | CLI (`apps/cli`), SDK (`packages/python-sdk`), engine (`engine/*`), modules (`modules/*`), policy + safety, scoring, report aggregation, agent-facing operations, CI behavior, configuration.           |
| **TypeScript / Node 20+** | Playwright runtime (`packages/ts-runtime`), MCP server (`packages/mcp-server` — pending ADR confirmation in), shared schemas (`packages/shared-schema`), browser-side instrumentation, runtime tracing. |

Cross-runtime communication is **explicit and structured** (JSON / JSONL today; a real protocol may be specified later as the runner matures). There is no shared memory, no in-process binding, no hidden coupling. The Python side spawns the TS runtime as a subprocess for Playwright execution.

Domain core in `engine/` MUST NOT depend directly on Typer, Click, FastAPI, Playwright, GitHub Actions, BrowserStack, or any LLM SDK. Each of these lives behind an adapter under `apps/`, `packages/`, or `integrations/`.

## Consequences

- **Positive:** Each runtime stays best-of-breed. Python keeps its strict type-checker (`mypy`) and lint stack (`ruff`); TypeScript keeps the Playwright-native dev loop. Neither runtime pretends to be the other.
- **Positive:** The JSONL bridge gives us a deterministic boundary we can record, replay, and version — which fits the "evidence in one place" thesis.
- **Negative / trade-off:** Two ecosystems mean two lockfiles (`uv.lock`, `pnpm-lock.yaml`), two test runners (`pytest`, `vitest`), two CI matrices, and contributors must be at least conversant in both. Documented in `docs/dev/local-setup.md`.
- **Negative / trade-off:** Spawning a subprocess per run adds a fixed startup cost. Acceptable today; revisitable if perf phases (12, 28) show it matters.
- **Follow-up obligations:** ships the JSONL contract as an explicit message schema; any future change to that contract requires a new ADR.

## Alternatives considered

- **Python-only with `pyppeteer` or `playwright-python`.** Rejected: the Playwright TypeScript SDK is the upstream-supported surface; the Python port lags features and trace semantics. SentinelQA's evidence-first thesis requires faithful Playwright behavior, not a port.
- **TypeScript-only.** Rejected: data scientists / security teams adopt Python tooling first; the SDK and MCP-friendly story is materially weaker on Node, and the LLM-agent integration story is much stronger when the surface is Python.
- **Polyglot via gRPC / WebSocket.** Rejected for release: the operational complexity of a long-running service between two runtimes outweighs the boundary benefit when the runs themselves are short-lived. JSONL over stdio is simple, debuggable, and version-tolerant.

## References

- the documentation Language strategy, §8.3 Architecture decisions, §15 TypeScript Runtime.
- our engineering rules§8 Runtime Ownership, §21 TypeScript / Playwright rules.
- Related ADRs: ADR-0001 (repository structure), ADR-0003 (package managers).
