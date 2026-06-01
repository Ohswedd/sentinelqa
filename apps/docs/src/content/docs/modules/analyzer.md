---
title: Analyzer module
description: Failure categorization, root-cause hypothesis, retry/quarantine decision.
status: Stable
---

The analyzer is a pure-function pipeline over `RunnerOutcome` records.
Eleven categorization rules map every failure onto the closed
the documentation ten-category set; the highest-confidence match wins; lower
matches are preserved as `secondary`.

Authority: the documentation, ADR-0014.

## Categories

`app_bug` · `test_bug` · `environment_failure` · `flake` ·
`data_setup_failure` · `auth_failure` · `api_failure` ·
`performance_regression` · `security_finding` ·
`accessibility_violation` · `unknown`.

## What it produces

- **Hypothesis** — interpolated from per-category templates with redacted snippets (URLs stripped of query/fragment + clipped at 80 chars; error messages clipped at 200).
- **Reproduction steps** — credential-free (auth pulled from `*_env` references); `build_repro_spec` emits a minimal banner-gated Playwright TS spec.
- **Retry decision** — `retry | quarantine_candidate | no_action`, hard two-retry cap.
- **Optional LLM refinement** — one sentence (≤ 400 chars) from the configured explainer; failures silently fall back to deterministic output.

The analyzer never raises. Pipeline failures degrade gracefully.
