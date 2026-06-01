---
title: Chaos module
description: Bounded Playwright-injected adversarial scenarios.
status: Stable
---

`sentinel chaos` exercises the app under stress: slow networks,
offline, API 500 / timeout, session expiry, double-submit races,
empty / large datasets, corrupted storage. Every scenario is bounded
— no unbounded slow modes, no infinite hangs.

Authority: the documentation, ADR-0028, our engineering rules §6.

## Thirteen scenarios

```
network slow_3g · offline · api_500 · api_timeout
session expired_token · missing_permissions
ux duplicate_submit · double_click_race · back_forward · refresh_mid_flow
data empty_dataset · large_dataset · storage_corruption
```

## Bounded by config

| Setting                | Range          | Why                                |
| ---------------------- | -------------- | ---------------------------------- |
| `slow_3g_kbps`         | 100..10 000    | Below 100 Kbps would amplify a DoS |
| `slow_3g_rtt_ms`       | 50..5 000      | No "infinite latency" mode         |
| `api_timeout_abort_ms` | 1 000..120 000 | No "hang forever" path             |
| `large_dataset_items`  | 100..10 000    | Bounded memory footprint           |

The module is `False` by default in `ModulesConfig`. The Phase 17
`nightly` preset enables it.

## CLI

```bash
uv run sentinel chaos --url http://127.0.0.1:5001 --scenarios slow_3g,api_500
```
