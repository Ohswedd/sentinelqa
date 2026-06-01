---
title: Architecture
description: Layered architecture of the SentinelQA engine.
status: Stable
---

SentinelQA is a layered system. The two hard rules are:

1. The **domain core** never depends on Typer, Playwright, FastAPI, or any vendor SDK.
2. External tools always sit **behind an adapter** so they can be replaced without touching the core.

## Layers

```
CLI / SDK / MCP / Plugin entry points ↓
Application services (engine.orchestrator, engine.reporter, engine.scoring) ↓
Domain core (engine.domain, engine.errors, engine.policy) ↓
Ports / protocols (CrawlBackend, A11yRunner, PerformanceRunner, …) ↓
Adapters / integrations (sentinel-ts subprocess, Docker runner, BrowserStack) ↓
External tools (Playwright, axe-core, httpx, cloud APIs)
```

## Runtime ownership

| Runtime    | Owns                                                                                     |
| ---------- | ---------------------------------------------------------------------------------------- |
| Python     | CLI, SDK, config, policy enforcement, scoring, reports, module orchestration, MCP server |
| TypeScript | Playwright execution, browser instrumentation, axe injection, performance observers      |

Communication between Python and TypeScript happens via NDJSON-framed
JSONL events on stdout (ADR-0009 / the documentation). No hidden coupling.

## Modules

Every audit capability is a `SentinelModule` instance with a
deterministic seven-step lifecycle :

```
validate prerequisites
plan checks
execute checks
collect evidence
emit findings
emit metrics
summarize result
```

Modules are discovered through a registry; the orchestrator drives the
lifecycle. A module failure produces a typed partial result unless the
whole run is invalidated.

## Run lifecycle

The audit runs a single canonical 17-step pipeline ([Run lifecycle](/concepts/run-lifecycle/)).
Safety policy is enforced exactly once, before any I/O. Dry-runs stop
after planning. Module errors mark the run `incomplete` (exit 6) without
crashing the run.

## Artifact tree

Every run writes to `.sentinel/runs/<run-id>/`:

```
run.json
config.snapshot.yaml
findings.json
score.json
report.html
report.md
junit.xml
sarif.json
traces/
screenshots/
videos/
logs/
audit.log
```

Machine-readable files carry schema versions. Scores are reproducible
from stored findings + metrics.
