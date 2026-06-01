---
title: API testing module
description: OpenAPI / GraphQL contract, negative cases, auth, latency, error-shape, backward-compat.
status: Stable
---

`sentinel api` exercises the target's HTTP API through `httpx` (no
Playwright). Negative cases come from a bounded named catalogue — no
fuzz library, no unbounded payloads.

Authority: the documentation, ADR-0027, our engineering rules §30.

## Seven check kinds

| Check             | What it does                                                |
| ----------------- | ----------------------------------------------------------- |
| `contract`        | OpenAPI 3.x / GraphQL SDL parse + per-request validation    |
| `negative`        | Bounded variant catalogue (missing-required, wrong-type, …) |
| `auth`            | Anonymous / expired-token / cross-user matrix               |
| `latency`         | Skip-only — defers to perf module                           |
| `pagination`      | Walks GETs with `page`/`cursor`/`offset`                    |
| `error_shape`     | Detects > 1 distinct rule-id per endpoint                   |
| `backward_compat` | Diff vs `--diff-since <run-id>` or last snapshot            |

## Layered no-fuzz guard

| Layer         | Limit                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------ |
| Config schema | `negative_max_payload_kb ∈ [1, 64]`, `negative_max_variants_per_endpoint ∈ [1, 16]`        |
| I/O layer     | `ABSOLUTE_MAX_REQUEST_BYTES = 64 KB` (raised before issuing)                               |
| Generator     | Fixed named catalogue — no fuzz library                                                    |
| CLI           | No `--aggressive`, `--fuzz`, `--brute`, `--stress`, `--unbounded`, `--no-rate-limit` flags |
| Tests         | AST + grep guard runs on every CI pass                                                     |

## CLI

```bash
uv run sentinel api --url http://127.0.0.1:5001 --openapi./openapi.json
```
