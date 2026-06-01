---
title: Run lifecycle
description: The 17-step canonical audit pipeline.
status: Stable
---

Every audit follows the same canonical pipeline. The steps are defined
in `engine.orchestrator.run_lifecycle.RunLifecycle.execute` and the
order is enforced by typed phase enums — modules cannot bypass it.

## The 17 steps

1. **load config**
2. **validate config**
3. **resolve target**
4. **enforce safety policy** — unsafe → exit 4, audit-log entry, run.json with `status="unsafe_blocked"`
5. **create run id** (`RUN-<ulid>`)
6. **create artifact directory** (`.sentinel/runs/<run-id>/`)
7. **snapshot config** (`config.snapshot.yaml`)
8. **discover app**
9. **build execution plan** — `--dry-run` stops here with `status="dry_run"`
10. **run modules** (Discovery → Planner → Generator → Runner → Analyzer → Functional → A11y → Perf → Security → LLM-Audit → API → Visual → Chaos; subset by config)
11. **collect evidence**
12. **normalize findings**
13. **calculate quality score**
14. **apply quality gates**
15. **generate reports**
16. **persist artifacts** (latest pointer, atomic writes)
17. **return deterministic exit code**

## Exit codes

| Code | Meaning               |
| ---- | --------------------- |
| 0    | Success               |
| 1    | Quality gate failed   |
| 2    | Invalid config        |
| 3    | Runtime error         |
| 4    | Unsafe target blocked |
| 5    | Dependency missing    |
| 6    | Test execution failed |
| 7    | Internal error        |

A successful run with critical blockers exits `1`, not `0`. The score
gate is the contract; the CI integration relies on it.

## Module errors

When a module raises inside step 10, the orchestrator catches the
exception, attaches the error to `ModuleOutcome.error_*`, and marks
the run **incomplete** — exit `6`, not `7`. Other modules continue to
run. The HTML report flags incomplete runs prominently.

## Audit log

Every step that touches user-visible state (write, network call,
safety decision, module result) emits a redacted JSONL entry to
`<run-dir>/audit.log`. This is the paper trail; the report's audit
panel reads it back.

## Determinism

The lifecycle is deterministic in the sense that re-running the same
inputs (same config, same target, same module versions) produces a
byte-identical `score.json`. This is enforced by a Hypothesis property
test in `tests/integration/scoring/` (5 000 examples, slow tier).
