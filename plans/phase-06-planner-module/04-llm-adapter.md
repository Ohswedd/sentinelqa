# Task 06.04 — LLM adapter (optional)

## Objective

Allow an LLM to augment the deterministic plan with additional flows or step refinements, behind a strict interface and a feature flag. Provider-agnostic; safe by default.

## Deliverables

- `engine/planner/llm_adapter.py` defining:
  - `class LlmPlanner(Protocol)` with `propose_flows(graph, risk, base_plan) -> list[Flow]`.
  - `class NullLlmPlanner` — default, returns `[]`. Used in CI and when no API key configured.
- `engine/planner/llm_providers/` containing thin adapters:
  - `openai_planner.py` (uses OpenAI Responses or Chat Completions API; requires `OPENAI_API_KEY`).
  - `anthropic_planner.py` (uses Anthropic Messages API; requires `ANTHROPIC_API_KEY`).
- Strict request contract: input is a redacted, sanitized representation of the graph (no PII, no credentials). System prompt locked in a versioned text file (`engine/planner/llm_prompts/planner.v1.md`) so changes require an ADR.
- Output validation: every proposed flow re-parsed through Pydantic; invalid flows discarded with a warning.
- Token / cost budget: hard cap per run (configurable; default $0.50 worth). If exceeded, stop and fall back to deterministic-only.
- Feature flag: `planner.llm.enabled: false` by default. CI default also false.

## Steps

1. Define the Protocol and the Null adapter.
2. Implement OpenAI + Anthropic adapters with retries, timeouts, and structured-output validation.
3. Add token-budget enforcement and an audit log entry per call.
4. Version the prompt file; ADR-0011 covers the prompt and the budget.

## Acceptance criteria

- With `planner.llm.enabled: false`, planning works without any API key.
- With `enabled: true` and a valid key, the adapter merges proposals into the plan, marking source `llm`.
- Invalid LLM output is dropped; planning never fails because of LLM behavior.
- Budget enforced.

## Tests required

- `tests/unit/planner/test_llm_adapter_null.py`.
- `tests/integration/planner/test_llm_adapter_openai.py` — uses VCR or stub HTTP server; never hits live API in CI.
- `tests/unit/planner/test_llm_output_validation.py` — malformed responses dropped.
- `tests/unit/planner/test_token_budget.py`.

## PRD / CLAUDE.md references

- PRD §6.8, open question 4 (provider-agnostic), §31.
- CLAUDE.md §15 Agent interface, §32 Error handling, §41 Telemetry (no source upload by default).

## Definition of Done

- [ ] Adapter Protocol + Null + two providers implemented.
- [ ] Prompt + budget under ADR.
- [ ] Tests cover null, mocked provider, malformed output, budget.
- [ ] `STATUS.md` updated.
