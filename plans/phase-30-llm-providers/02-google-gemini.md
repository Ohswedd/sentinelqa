# Task 30.02 — Google Gemini adapter

## Deliverables

- `engine/llm/providers/gemini.py` — `GeminiProvider` implementing
  `LlmProvider`. Calls Google AI Studio's REST endpoint
  `https://generativelanguage.googleapis.com/v1/models/<model>:generateContent`
  via `httpx`. No `google-generativeai` SDK.
- `GeminiProvider.complete(request)` translates `LlmRequest.messages`
  into Gemini's `contents` array (role-mapped). For structured output it
  uses Gemini's `responseSchema` + `responseMimeType: application/json`
  and re-validates the returned JSON against the request's `response_schema`.
- API key read from `GEMINI_API_KEY` env var at call time. Adapter never
  logs the key.
- Cost mapping table in `gemini_pricing.py` for the supported models
  (default `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash`).
  Cost is computed from `usageMetadata.{promptTokenCount,
  candidatesTokenCount}` × the table; recorded on every `LlmResponse`.
- `doctor()` issues a 1-token probe with a hardcoded "ping" prompt and
  reports `available` / `degraded` / `unavailable` + the latency.

## Tests required

- `tests/unit/llm/providers/test_gemini.py` — mocked happy path, schema
  validation failure, 401 missing key, 429 rate-limited, budget overrun.
  Uses `httpx.MockTransport`.
- `tests/integration/llm/test_gemini_structured_output.py` — feeds the
  planner's locked `planner.v1.md` prompt; asserts the `_ProposalEnvelope`
  validation still holds end-to-end.

## Definition of Done

- [ ] No `google-generativeai` import anywhere in the repo (lint guard).
- [ ] Adapter green under mocks.
- [ ] `sentinel.config.yaml.example` documents the `planner.llm.provider:
      "gemini"` block.
- [ ] `STATUS.md` updated.
