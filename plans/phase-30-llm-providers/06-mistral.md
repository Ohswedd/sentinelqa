# Task 30.06 — Mistral adapter

## Deliverables

- `engine/llm/providers/mistral.py` — `MistralProvider`. Calls Mistral
  La Plateforme's REST endpoint at
  `https://api.mistral.ai/v1/chat/completions` via `httpx`. No `mistralai`
  SDK.
- Auth `Authorization: Bearer <MISTRAL_API_KEY>`.
- Structured output via `response_format: { type: "json_schema",
  json_schema: { name, schema, strict: true } }`. Re-validates client-
  side against the request's `response_schema`.
- Default models: `mistral-large-latest`, `mistral-small-latest`,
  `open-mistral-nemo`.
- Cost mapping from `usage.prompt_tokens` + `usage.completion_tokens` ×
  the per-model table.

## Tests required

- `tests/unit/llm/providers/test_mistral.py` — mocked happy path, 401,
  structured-output enforcement.
- `tests/integration/llm/test_mistral_structured.py` — planner-prompt
  round-trip.

## Definition of Done

- [ ] Adapter green under mocks.
- [ ] No `mistralai` import anywhere.
- [ ] `STATUS.md` updated.
