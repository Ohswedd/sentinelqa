---
title: sentinel doctor
description: Diagnose the local environment before running an audit.
status: Stable
---

`sentinel doctor` validates your local environment against the
prerequisites SentinelQA needs to run an audit. It is the first command
you should run after install and the first command CI should run before
spending compute on an audit.

## What it checks

| Check                 | What good looks like                                  |
| --------------------- | ----------------------------------------------------- |
| Python version        | 3.11 or 3.12                                          |
| Node version          | 20 or 22                                              |
| Playwright            | browsers installed under the workspace cache          |
| Config                | `sentinel.config.yaml` parses, no inline secrets      |
| Safety                | resolved target is local OR in `target.allowed_hosts` |
| Reachability          | resolved target answers within the configured timeout |
| Env vars              | every `*_env` reference resolves to a non-empty value |
| `.sentinel/` writable | run artifacts have a home                             |
| Disk                  | ≥ 1 GiB free on the partition holding `.sentinel/`    |

## Modes

```bash
uv run sentinel doctor # human ASCII output
uv run sentinel doctor --json # single-line JSON
```

The JSON form is the contract for CI; the ASCII form is for humans.

## Exit codes

| Code | Meaning                                                    |
| ---- | ---------------------------------------------------------- |
| 0    | All checks passed                                          |
| 2    | Config or CLI usage error                                  |
| 3    | Runtime error                                              |
| 4    | Unsafe target                                              |
| 5    | Missing dependency (Node, pnpm, Playwright, `sentinel-ts`) |

A non-zero exit means do not run an audit — the failure mode would be
indistinguishable from a real bug.
