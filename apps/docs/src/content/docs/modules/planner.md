---
title: Planner module
description: Deterministic-first test plan generator with an opt-in LLM adapter.
status: Stable
---

The planner translates the discovery output into a `TestPlan`: an
ordered list of `Flow`s with priorities, coverage estimates, and
optional LLM-suggested refinements.

Authority: PRD §9.2, ADR-0011.

## Determinism first

Eleven named extractors run over routes / forms / APIs / auth
boundaries:

- LoginFlowExtractor
- SignupFlowExtractor
- LogoutFlowExtractor
- PasswordResetFlowExtractor
- CrudFlowExtractor
- SearchFilterSortFlowExtractor
- AdminFlowExtractor
- RoleFlowExtractor
- FileUploadDownloadFlowExtractor
- PaymentSandboxFlowExtractor
- NotificationFlowExtractor

Each emits flows with a confidence in `[0, 1]`. Flows below the
`PROPOSAL_THRESHOLD` (0.5) get a `confidence_low` tag.

## Optional LLM adapter

Set `planner.llm.enabled: true` and configure a provider
(`openai` or `anthropic`). The locked prompt lives at
`engine/planner/llm_prompts/planner.v1.md` and is version-pinned via
`PROMPT_VERSION`. Per-run spend is bounded by `planner.llm.max_usd_per_run`
(default $0.50).

## CLI

```bash
uv run sentinel plan --url http://127.0.0.1:5001 --from-discovery
```

Outputs `plan.json` (byte-stable across re-runs with the same inputs)
plus `plan.md` for humans.
