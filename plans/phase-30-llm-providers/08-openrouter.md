# Task 30.08 — OpenRouter (gateway) adapter

## Deliverables

- `engine/llm/providers/openrouter.py` — `OpenRouterProvider`. Calls
  OpenRouter's OpenAI-compatible endpoint at
  `https://openrouter.ai/api/v1/chat/completions` via `httpx`. No
  `openrouter` SDK (none exists publicly; the surface is REST).
- Auth `Authorization: Bearer <OPENROUTER_API_KEY>`, plus the polite
  identification headers OpenRouter recommends
  (`HTTP-Referer: https://github.com/Ohswedd/sentinelqa`,
  `X-Title: SentinelQA`).
- Model strings are namespaced (`anthropic/claude-3.5-sonnet`,
  `google/gemini-2.0-flash`, `meta-llama/llama-3.1-70b-instruct`, etc.).
  The provider's `doctor()` lists which models are currently routable
  for the caller via `GET /api/v1/models`.
- Cost mapping is OpenRouter-driven: each response includes its
  computed cost on the `usage.cost` field (USD). The adapter trusts
  that value (it is the billable amount) rather than re-deriving from a
  per-model table.
- Structured output via the standard OpenAI `response_format` envelope;
  client-side re-validation per the shared protocol.

## Tests required

- `tests/unit/llm/providers/test_openrouter.py` — mocked happy path,
  401, model-not-found, `usage.cost` propagation.

## Definition of Done

- [ ] Adapter green under mocks.
- [ ] `HTTP-Referer` + `X-Title` headers verified by test fixture.
- [ ] `STATUS.md` updated.
