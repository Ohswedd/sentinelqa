# Task 09.05 — LLM explainer adapter (optional)

## Objective

Allow an LLM to refine the analyzer's root-cause hypothesis with natural-language explanations, behind a Protocol + feature flag.

## Deliverables

- `engine/analyzer/llm_explainer.py` mirroring the Planner's LLM-adapter pattern: Protocol, Null impl, OpenAI/Anthropic adapters.
- Strict redaction of inputs (no secrets, no raw cookies, no PII).
- Output is appended to the deterministic hypothesis under `llm_refinement`, never replaces it.
- Token budget per run.
- Feature flag: `analyzer.llm.enabled: false` by default.

## Steps

1. Mirror the Planner adapter shape.
2. Tests.

## Acceptance criteria

- With LLM disabled, analyzer still produces a complete hypothesis.
- With LLM enabled, the refinement is added without removing the deterministic part.

## Tests required

- `tests/unit/analyzer/test_llm_null.py`.
- `tests/integration/analyzer/test_llm_explainer_mocked.py`.

## PRD / CLAUDE.md references

- PRD §6.8, §9.5.
- CLAUDE.md §15, §32.

## Definition of Done

- [ ] Adapter present, disabled by default, tested.
- [ ] `STATUS.md` updated.
