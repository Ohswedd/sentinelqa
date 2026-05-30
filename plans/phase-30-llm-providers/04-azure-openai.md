# Task 30.04 — Azure OpenAI adapter

## Deliverables

- `engine/llm/providers/azure_openai.py` — `AzureOpenAiProvider`. Calls
  the Azure OpenAI REST endpoint at
  `https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=<apiver>`
  via `httpx`. No `openai` SDK.
- Auth header `api-key: <AZURE_OPENAI_API_KEY>`. The
  `<resource>` / `<deployment>` / `<apiver>` triple is config-driven:
  `planner.llm.azure.{resource, deployment, api_version}`.
- Request body identical to OpenAI Chat Completions; the existing
  `engine/planner/providers/openai_planner.py` payload builder is
  factored out and reused. Structured output via the
  `response_format: { type: "json_schema", json_schema: {...} }` envelope
  on `api-version=2024-08-01-preview` and later.
- Cost mapping table for the deployments the user pins (defaults match
  the standard Azure pricing surface; computed from `usage.prompt_tokens`
  + `usage.completion_tokens`).

## Tests required

- `tests/unit/llm/providers/test_azure_openai.py` — mocked happy path,
  401 with the auth-header form (not `Authorization: Bearer`), 404 on
  unknown deployment, schema mismatch.
- `tests/integration/llm/test_azure_openai_structured.py` — planner
  prompt round-trip via `httpx.MockTransport`.

## Definition of Done

- [ ] Adapter green under mocks.
- [ ] `openai` import banned (lint guard).
- [ ] `sentinel.config.yaml.example` documents `planner.llm.azure.*`.
- [ ] `STATUS.md` updated.
