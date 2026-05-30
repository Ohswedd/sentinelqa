# Task 30.07 — Groq adapter

## Deliverables

- `engine/llm/providers/groq.py` — `GroqProvider`. Calls Groq Cloud's
  OpenAI-compatible endpoint at
  `https://api.groq.com/openai/v1/chat/completions` via `httpx`. No
  `groq` SDK.
- Auth `Authorization: Bearer <GROQ_API_KEY>`.
- Structured output via Groq's `response_format` flag; same shape as
  OpenAI but the supported models are a smaller set
  (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`,
  `mixtral-8x7b-32768`).
- Cost is **deliberately set to `0.0` if Groq's free tier is detected**
  (no `Authorization` header). When paid, cost is computed from
  `usage.prompt_tokens` + `usage.completion_tokens` × the per-model
  table.
- Headline value: latency. The adapter records `latency_ms` and surfaces
  it in `sentinel llm doctor` so users can compare providers.

## Tests required

- `tests/unit/llm/providers/test_groq.py` — mocked happy path, 401,
  rate-limited.

## Definition of Done

- [ ] Adapter green under mocks.
- [ ] No `groq` SDK in `pyproject.toml`.
- [ ] `STATUS.md` updated.
