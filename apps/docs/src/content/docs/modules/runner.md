---
title: Runner module
description: Local + Docker Playwright runners with retry, quarantine, and sharding.
status: Stable
---

The runner executes generated specs against the target and turns the
result into a typed `RunnerOutcome` with per-test executions, P50/P95
metrics, and a per-module status.

.

## Two runners, one contract

| Runner         | When to use                                      |
| -------------- | ------------------------------------------------ |
| `LocalRunner`  | Default; spawns `sentinel-ts run` via subprocess |
| `DockerRunner` | CI; pinned Playwright image; isolated filesystem |

Both implement `RunnerInvocation → RunnerOutcome`. Switch via
`runner.docker: true` in config.

## Sharding

Deterministic via `sha1(test_path) % total`. Set `runner.shards: "1/4"`
to run shard 1 of 4. The aggregator merges shards by `test_id` and
picks the worst per-test status.

## Retry + quarantine

- `runner.retries.max` — up to 2 (the engineering guidelines: hard cap).
- `runner.quarantine.path` — YAML list with `test_id`, `reason`, `expires_at` (≤ today + 14 days), `issue_url` (https only). Expired entries fail the load.

Quarantine is a humane mute, not silent muting: every quarantined
test is logged and counted; the cap prevents drift.

## CLI

```bash
uv run sentinel test --url http://127.0.0.1:5001 --workers 4
```
