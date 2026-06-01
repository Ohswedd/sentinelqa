---
title: Performance module
description: Synthetic page / API / CPU / leak budgets with explicit RUM disclaimer.
status: Stable
---

`sentinel perf` measures page-load, API, bundle, long-task, and
navigation-stability metrics against budgets. Results are **synthetic**
— measured in a controlled Chromium, not real users.

.

## Wording contract

Every finding begins with **"Synthetic performance check"** and carries
an explicit "not Real-User Monitoring" disclaimer. The guard test
`tests/security/test_synthetic_perf_labeling.py` forbids stronger
claims anywhere in product output.

## What it measures

| Capability     | Metric                                             |
| -------------- | -------------------------------------------------- |
| Page budget    | median LCP, TTFB, INP, CLS                         |
| API latency    | P50 / P95 per templated endpoint (`min_samples=5`) |
| Bundle size    | gzipped JS bytes per route                         |
| CPU long tasks | total long-task time, count per route              |
| Nav stability  | first-to-last DOM growth %, heap growth %          |

## Severity

Page / CPU / bundle overage > 50 % → high, else medium. API P95
overage > 100 % → high, else medium. Nav-stability is `low` with
confidence 0.5 (heuristic).

## CLI

```bash
uv run sentinel perf --url http://127.0.0.1:5001 --samples 5
```
