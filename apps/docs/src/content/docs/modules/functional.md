---
title: Functional module
description: Drive generated and user-authored Playwright specs.
status: Stable
---

`sentinel functional` walks `tests/sentinel/` for `*.spec.ts`, drives
them through the [Runner](/modules/runner/), and translates failed
executions into typed findings with our product spec evidence.

.

## Modes

- `smoke` — `@p0` only (smoke-suite contract)
- `standard` — `@p0` + `@p1`
- `full` — everything

Combine with `--grep <pattern>` to intersect:

```bash
uv run sentinel functional --mode smoke --grep '@p0.*login'
```

## Tags

The generator emits a canonical tag set on every spec, in order:

```
@p0..p3 @module:<name> @flow:<extractor> @risk:<level>
```

Plus any planner-attached tags (alphabetized, IDs stripped).

## Exit codes

| Code | Meaning                                            |
| ---- | -------------------------------------------------- |
| 0    | All tests passed                                   |
| 1    | Quality gate failed (e.g. flake-rate above policy) |
| 2    | Config / shard / mode error                        |
| 4    | Unsafe target                                      |
| 5    | `sentinel-ts` missing                              |
| 6    | Runner error                                       |
