# ADR-0042: Canonical multi-provider LLM adapter layer

## Status

Accepted

<!-- Date: 2026-05-31 -->
<!-- Authors: @ohswedd -->

## Context

ADR-0037 ("Provider-agnostic LLM access through adapters") committed
SentinelQA to a Protocol-based, HTTP-only LLM surface so callers don't
get locked to one vendor. Phase 06 (planner) and Phase 09 (analyzer)
each shipped their own caller-specific Protocol — `LlmPlanner` and
`LlmExplainer` respectively — with HTTP adapters for OpenAI Chat
Completions and Anthropic Messages. Two providers, two duplicated
adapter trees.

Phase 30 (post-MVP ecosystem expansion, see `plans/STATUS.md`) needs
seven additional providers: Google Gemini (AI Studio), Ollama (local),
Azure OpenAI, Google Vertex AI, Mistral, Groq, and OpenRouter
(gateway). Continuing the per-caller-Protocol pattern would have meant
implementing each of the seven providers twice (once for the planner,
once for the analyzer) — and three times when Phase 20's healer also
starts wanting LLM-driven repair proposals.

CLAUDE.md §6 forbids stealth / evasion / unauthorized capabilities;
§33 forbids inline secrets; §35 prefers small, well-maintained deps.
We also have a self-imposed rule: never import a vendor SDK when
`httpx` can do the job. Reasons: (a) we don't want to pin SentinelQA
to a vendor's release cadence, (b) we don't want to ship `openai +
anthropic + google-genai + google-cloud-aiplatform + mistralai + groq`
as transitive deps just for a few HTTP POSTs, (c) mocking `httpx`
beats mocking a vendor SDK.

## Decision

Introduce a canonical, single Protocol — `engine.llm.LlmProvider` —
that every adapter implements:

```python
@runtime_checkable
class LlmProvider(Protocol):
    name: ClassVar[str]
    version: ClassVar[str]
    def complete(self, request: LlmRequest) -> LlmResponse: ...
    def doctor(self) -> ProviderHealth: ...
```

Caller-specific shape is carried by the `LlmRequest`:

- `system` + `messages` + `response_schema` (structured output, JSON
  Schema Draft 2020-12 subset).
- `caller` ∈ {`planner`, `analyzer`, `healer`, `doctor`, `test`} —
  used for cost attribution and audit-log routing.
- `run_id` — pinned to the active SentinelQA run for cross-reference.

Every provider returns an `LlmResponse` with pre-validated `parsed`
JSON, token `usage`, `cost_usd`, `latency_ms`, `provider`, and
`model`. A graceful-degradation flag `available: bool` lets the
caller fall back to the deterministic path without raising (Ollama
when the local server is offline).

Each provider is implemented as an `httpx`-only adapter under
`engine/llm/providers/`. Nine providers ship in Phase 30:

| Provider       | Endpoint                                                                                                        | Auth                                                 | Model strings                                                           |
| -------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------- |
| `anthropic`    | `api.anthropic.com/v1/messages`                                                                                 | `x-api-key`                                          | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-…`                      |
| `openai`       | `api.openai.com/v1/chat/completions`                                                                            | `Authorization: Bearer`                              | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`                                  |
| `gemini`       | `generativelanguage.googleapis.com/v1/models/<m>:generateContent`                                               | `x-goog-api-key`                                     | `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash`                |
| `ollama`       | `localhost:11434/api/chat` (configurable host)                                                                  | _none_                                               | `qwen2.5-coder:7b` and any locally-pulled model                         |
| `azure_openai` | `<resource>.openai.azure.com/openai/deployments/<d>/chat/completions`                                           | `api-key`                                            | per-deployment                                                          |
| `vertex`       | `<region>-aiplatform.googleapis.com/v1/projects/<p>/locations/<r>/publishers/google/models/<m>:generateContent` | OAuth2 access token (RS256 JWT exchange)             | `gemini-*` models on Vertex                                             |
| `mistral`      | `api.mistral.ai/v1/chat/completions`                                                                            | `Authorization: Bearer`                              | `mistral-large-latest`, `mistral-small-latest`, `open-mistral-nemo`     |
| `groq`         | `api.groq.com/openai/v1/chat/completions`                                                                       | `Authorization: Bearer`                              | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768` |
| `openrouter`   | `openrouter.ai/api/v1/chat/completions`                                                                         | `Authorization: Bearer` + `HTTP-Referer` + `X-Title` | namespaced (`anthropic/claude-…`, `meta-llama/llama-…`)                 |

Plus the always-available `null` provider — returns
`available=False`, cost `0.0`, no remote endpoint.

**Vertex AI's only new dependency is `cryptography` (PyCA, pinned
`45.0.1`) for RS256 JWT signing against a service-account private
key. Not `google-auth`, not `google-cloud-aiplatform` — just the
canonical Python crypto library.** Justified under CLAUDE.md §35:
necessary, maintained, BSD/Apache dual-licensed, audited, and
materially smaller than the alternatives.

### Shared infrastructure

- `engine/llm/budget.py` — per-run `LlmBudget` with a global cap
  (`max_usd_per_run`, default 0.50 USD) and per-caller sub-caps
  (`max_usd_planner` / `_analyzer` / `_healer`). Every adapter calls
  `budget.pre_check(estimate)` before sending and `budget.add(actual)`
  on completion. Overrun raises `LlmBudgetExceededError` (exit
  `E-LLM-003`).
- `engine/llm/rate_limit.py` — per-provider token bucket (default 60
  requests/min). Empty bucket → `LlmRateLimitedError` (exit
  `E-LLM-007`).
- `engine/llm/redaction.py` — outgoing request bodies and incoming
  response bodies are summarized (NEVER logged verbatim) before they
  reach the audit log. Prompts and response text are excluded by
  default; the audit log is for accountability, not prompt
  debugging.
- `engine/llm/registry.py` — `register_provider` + `resolve_provider`
  - `list_providers`. Provider factories are lazy — concrete adapter
    modules are imported only when their name is resolved, so the cold
    `sentinel --version` path stays fast.

### Error grid (`engine/errors/codes.py`)

Codes `E-LLM-001..009` added:

- `E-LLM-001` Missing key (exit 5).
- `E-LLM-002` Model unavailable (exit 5).
- `E-LLM-003` Budget exceeded (exit 1).
- `E-LLM-004` Request rejected (exit 3).
- `E-LLM-005` Response validation failed (exit 3).
- `E-LLM-006` Timeout (exit 3).
- `E-LLM-007` Rate-limited (exit 3).
- `E-LLM-008` Caller-side schema mismatch (exit 3).
- `E-LLM-009` Structured output not supported (exit 2).

### Backwards compatibility

- `engine.planner.llm_adapter.LlmPlanner` and
  `engine.analyzer.llm_explainer.LlmExplainer` Protocols are
  unchanged. Their existing OpenAI / Anthropic HTTP adapters
  (`engine/planner/llm_providers/`, `engine/analyzer/llm_providers/`)
  continue to ship and the Phase-06/09 planner/analyzer pipelines
  continue to use them.
- `BudgetExceededError`, `LlmUsage`, `estimate_cost_usd`, and
  `ensure_within_budget` are re-exported from `engine.llm.budget` to
  the existing call sites; the new `BudgetExceededError` is BOTH a
  `RuntimeError` (for `except RuntimeError:` blocks in planner /
  analyzer) AND a `SentinelError` (for the new typed lifecycle).
- The Phase-30 `sentinel llm` CLI (`list` / `doctor` / `price`) sees
  the entire 10-provider registry; it does not distinguish "old" from
  "new."

## Consequences

- New consumers (healer, future LLM-augmented modules) implement once
  against `LlmProvider`; the planner/analyzer migrations happen on
  the next refactor pass.
- The `cryptography` runtime dep is new but small and well-maintained;
  far smaller surface than `google-auth` + `google-cloud-aiplatform`
  would have been.
- Provider authors don't need to subclass anything ad-hoc — they
  inherit from `engine.llm.providers._http_base.HttpLlmProviderBase`
  and override four methods: `endpoint_url`, `auth_headers`,
  `build_payload`, `extract_response_text` (+ optional
  `usage_from_response`, `cost_from_response`, `doctor`).
- Cost-table accuracy stays the user's responsibility. We pin sane
  defaults (per-1k-token rates for each known model at adapter
  authorship time) and surface them via `sentinel llm price`; users
  who negotiate custom rates with their vendor can override via the
  config (`llm.providers.<name>.models` + future pricing-override
  hook).
- Cold-path performance: registry stays lazy. `import engine.llm`
  registers 10 factories without importing any concrete adapter
  module — `sentinel --version` and `sentinel doctor` are unaffected
  (see `docs/release/perf-audit-2026-05-30.md`).

## Alternatives considered

1. **One vendor SDK per provider.** Rejected — 6+ heavy SDKs in
   `pyproject.toml`, mocking pain, vendor release coupling.
2. **A single `LiteLLM`-style gateway dep.** Rejected — adds a
   ~200KB+ Python dep that itself imports each vendor SDK, and
   couples our reliability to a third party. We already have the
   abstraction we need with `LlmProvider`.
3. **Keep per-caller Protocols, duplicate adapters.** Rejected for
   the obvious O(callers × providers) cost as the matrix grows.
4. **Require `google-auth` for Vertex.** Rejected — that package
   pulls in `google-cloud-core`, `googleapis-common-protos`, and a
   transitive grpcio tail; for SentinelQA's scope (a single JWT
   exchange every hour) the canonical `cryptography` library is the
   right unit of dependency cost.

## References

- ADR-0011 Planner deterministic vs LLM.
- ADR-0014 Analyzer LLM explainer.
- ADR-0037 LLM provider-agnostic adapters.
- CLAUDE.md §6 (safety), §33 (secrets), §35 (deps).
- `engine/llm/protocol.py`, `engine/llm/budget.py`,
  `engine/llm/providers/*.py`.
- `plans/phase-30-llm-providers/` task files.
