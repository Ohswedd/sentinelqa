# Phase 30 — Multi-Provider LLM Adapter Layer

## Objective

Generalise the Phase 06 planner's HTTP-only LLM adapters (OpenAI Chat
Completions + Anthropic Messages) into a provider-agnostic surface that the
planner, analyzer, healer, and any future LLM-augmented module can share. Add
adapters for **seven additional providers** so SentinelQA isn't single-vendor
locked: Google Gemini, Ollama (local), Azure OpenAI, Google Vertex AI,
Mistral, Groq, OpenRouter (gateway).

Hard constraint (CLAUDE.md §35, §6): every adapter must be HTTP-only via
`httpx` — no vendor SDK, no proxy, no shared SentinelQA API key. The user
brings their own credentials, scoped to their tenancy. Every adapter inherits
the existing redaction, per-run cost budget, and rate-limit policy.

## PRD / CLAUDE.md references

- PRD §6 (provider-agnostic principle), §9.2 (planner LLM), §9.5 (analyzer
  LLM), ADR-0011 (planner deterministic vs LLM), ADR-0037 (LLM
  provider-agnostic).
- CLAUDE.md §15 (Agent interface), §33 (Logging and Secrets), §35
  (Dependency rules — no vendor SDKs for what `httpx` can do).

## Sub-phases & tasks

1. `01-llm-protocol.md` — Pull the per-task `LlmPlanner` and `LlmExplainer`
   Protocols into a single canonical `engine.llm.LlmProvider` surface with
   a structured-output contract and shared cost / budget / redaction
   plumbing.
2. `02-google-gemini.md` — `GeminiProvider` adapter (Google AI Studio API).
3. `03-ollama-local.md` — `OllamaProvider` adapter (localhost; no key).
4. `04-azure-openai.md` — `AzureOpenAiProvider` adapter (Azure deployments).
5. `05-vertex-ai.md` — `VertexAiProvider` adapter (Google Vertex AI).
6. `06-mistral.md` — `MistralProvider` adapter (Mistral La Plateforme).
7. `07-groq.md` — `GroqProvider` adapter (Groq Cloud).
8. `08-openrouter.md` — `OpenRouterProvider` adapter (gateway pattern).
9. `09-cost-budget-shared.md` — Lift per-provider cost / token / RPS guards
   into a shared `engine.llm.budget` so every consumer enforces the same
   policy.
10. `10-cli-and-doctor.md` — `sentinel llm list`, `sentinel llm doctor`,
    config schema additions, error-code additions.

## Definition of Done

- Every new adapter is HTTP-only via `httpx`. No vendor SDK dependency.
- Every adapter rejects missing-key + budget-overrun cleanly with the
  canonical error grid.
- Every adapter has a unit test using `httpx.MockTransport` and an
  integration test that asserts the locked prompt envelope still validates
  against `_ProposalEnvelope`.
- Planner + analyzer + healer can be reconfigured to use any of the nine
  providers via `*.llm.provider: "<name>"` in `sentinel.config.yaml`.
- ADR-0042 (Multi-provider LLM adapter layer) accepted.
- PRD §9.2 / §9.5 / §15.7 updated with the new provider list.
- Coverage gate met (engine.llm ≥ 90 % per file).

## Phase Gate Review

- [ ] Nine providers green under mocks.
- [ ] `sentinel llm doctor` reports per-provider reachability.
- [ ] No SDK added to `pyproject.toml` for any provider.
- [ ] ADR-0042 accepted.
- [ ] PRD updated.
- [ ] `STATUS.md` updated.
