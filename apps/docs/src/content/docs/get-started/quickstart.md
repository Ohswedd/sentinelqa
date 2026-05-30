---
title: Quickstart
description: Run your first SentinelQA audit in five minutes.
status: Stable
---

This page walks through a complete audit of one of the bundled example
apps. It is timed to take under five minutes on a fresh laptop.

## 1. Boot the example app

```bash
make demo-flask
```

This launches the Flask demo at `http://127.0.0.1:5001`. The app
loop-back binds only; SentinelQA refuses to point at non-loopback
targets without an explicit allowlist.

## 2. Configure the audit

The bundled `examples/flask/sentinel.config.yaml` is already set up —
target points at the loopback URL, all modules enabled, score floor 80.

## 3. Run the audit

```bash
cd examples/flask
uv run sentinel audit
```

You will see:

- Discovery phase (HTTP crawl)
- Planner phase (deterministic flows)
- Generator phase (Playwright specs into `tests/sentinel/`)
- Runner phase (local Playwright)
- Findings + score + release decision

## 4. View the report

```bash
uv run sentinel report --latest --format html --open
```

Look for:

- Total quality score
- Per-module result cards
- Findings table with severity / module filters
- Audit trail panel

## 5. Tear down

```bash
make demo-down
```

## What just happened

The audit ran the canonical 17-step
[run lifecycle](/concepts/run-lifecycle/), enforced the
[safety policy](/concepts/safety-boundary/), and persisted every
artifact under `.sentinel/runs/<run-id>/`.

For a deeper walkthrough see
[Run your first audit](/get-started/first-audit/).
