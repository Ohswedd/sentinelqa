---
title: Modules
description: All audit capabilities ship as modules with a deterministic lifecycle.
status: Stable
---

Every SentinelQA capability is implemented as a **module**: a
self-registering subclass of `SentinelModule` with a fixed seven-step
lifecycle.

Authority: CLAUDE.md §9, PRD §10.

## Lifecycle

```
validate prerequisites
plan checks
execute checks
collect evidence
emit findings
emit metrics
summarize result
```

The orchestrator drives this lifecycle. A module failure produces a
typed partial result; other modules continue.

## Module status

| Module         | CLI                   | Status | Notes                                                         |
| -------------- | --------------------- | ------ | ------------------------------------------------------------- |
| Functional     | `sentinel functional` | Stable | Playwright runs of generated/user specs                       |
| Accessibility  | `sentinel a11y`       | Stable | axe-core + deterministic keyboard / landmark / sr-name checks |
| Performance    | `sentinel perf`       | Stable | Synthetic LCP/TTFB/INP/CLS + API P50/P95 budgets              |
| Security       | `sentinel security`   | Stable | Safe HTTP checks, gated probes, dep + SAST adapters           |
| LLM-Code Audit | `sentinel llm-audit`  | Stable | 16 PRD §10.9 anti-pattern detectors                           |
| Visual         | `sentinel visual`     | Stable | Pillow diff, hard CI-acceptance guard                         |
| API            | `sentinel api`        | Stable | OpenAPI/GraphQL contract + negative + auth checks             |
| Chaos          | `sentinel chaos`      | Stable | Bounded Playwright-injected scenarios                         |
| Healer         | `sentinel fix`        | Stable | Locator / wait / fixture proposals, banner-aware apply        |

Each module page documents its options, exit codes, and the rule
catalog it ships.

## Wire format

Every module persists a typed result under
`<run-dir>/<module>/<check>.json` plus an `index.json` aggregate.
Schemas live under `packages/shared-schema/` and are checked into
`engine.domain` Pydantic models.

## Quality gates

Modules emit `Finding` records with severity (`critical | high | medium | low | info`)
and confidence (`0..1`). The scoring engine ([Quality scoring](/cli/#sentinel-report)))
turns those into the run's `score.json` and release decision.

## Adding a module

See [Plugins](/plugins/) for how to ship an out-of-tree module via the
`sentinelqa.plugins` entry-point group.
