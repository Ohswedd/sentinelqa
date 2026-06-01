# LLM providers

SentinelQA's planner, analyzer, healer, and future LLM-augmented
modules speak to a fleet of LLM providers behind one canonical Protocol
— `engine.llm.LlmProvider` (Phase 30, ADR-0042). Ten providers ship
out of the box:

| Provider       | Env var                          | Auth                    | Default model                 | Notes                                                                |
| -------------- | -------------------------------- | ----------------------- | ----------------------------- | -------------------------------------------------------------------- |
| `null`         | —                                | none                    | —                             | Always returns `available=False`. No API calls.                      |
| `anthropic`    | `ANTHROPIC_API_KEY`              | `x-api-key`             | `claude-3-5-sonnet-20241022`  | Messages API.                                                        |
| `openai`       | `OPENAI_API_KEY`                 | `Authorization: Bearer` | `gpt-4o-mini`                 | Chat Completions, `response_format: json_schema`.                    |
| `gemini`       | `GEMINI_API_KEY`                 | `x-goog-api-key`        | `gemini-1.5-flash`            | Google AI Studio REST.                                               |
| `ollama`       | _none_ (local)                   | none                    | `qwen2.5-coder:7b`            | Offline default; cost always `0.0`.                                  |
| `azure_openai` | `AZURE_OPENAI_API_KEY`           | `api-key:`              | per-deployment                | Configure `azure_resource`, `azure_deployment`, `azure_api_version`. |
| `vertex`       | `GOOGLE_APPLICATION_CREDENTIALS` | OAuth2 (JWT)            | `gemini-1.5-flash`            | RS256 JWT signed via PyCA `cryptography`. No `google-auth` SDK.      |
| `mistral`      | `MISTRAL_API_KEY`                | `Authorization: Bearer` | `mistral-small-latest`        | `response_format: json_schema` (strict).                             |
| `groq`         | `GROQ_API_KEY`                   | `Authorization: Bearer` | `llama-3.1-8b-instant`        | OpenAI-compatible; latency-forward.                                  |
| `openrouter`   | `OPENROUTER_API_KEY`             | `Authorization: Bearer` | `anthropic/claude-3.5-sonnet` | Gateway; trusts `usage.cost` for billing.                            |

## Hard constraints

- **HTTP-only.** Every adapter speaks REST via `httpx`. No vendor SDK is imported anywhere in the codebase.
- **Bring your own credentials.** API keys come from env vars by name only. Inline secrets are never accepted in `sentinel.config.yaml` .
- **Per-run cost budget.** Every call passes through `LlmBudget`. The default cap is **$0.50 per run**; per-caller sub-caps (planner / analyzer / healer) are optional. Budget overrun raises `LlmBudgetExceededError` (exit `E-LLM-003`) and the caller falls back to its deterministic path.
- **Rate-limit.** Each provider has its own token-bucket; default 60 requests/min.
- **Audit-log redaction.** Outgoing request bodies and incoming response bodies are summarized before logging — prompt text and response text NEVER touch the audit log by default.

## Picking a provider

- **You want offline / air-gapped.** → `ollama`. No API key, no network egress beyond `localhost`. Pull a model first (e.g. `ollama pull qwen2.5-coder:7b`).
- **You want the absolute lowest cost.** → `groq` (free tier on `llama-3.1-8b-instant`) or `gemini` (`gemini-1.5-flash` at $0.075/$0.30 per 1M tokens).
- **You want the best quality for code / repair tasks.** → `anthropic` (`claude-3-5-sonnet-20241022`).
- **You're enterprise on Azure.** → `azure_openai`. Bring your own deployment.
- **You're enterprise on GCP.** → `vertex`. Service-account JWT.
- **You want to A/B many models cheaply.** → `openrouter`. Single API key, many namespaced models, vendor billing.

## CLI

```
$ sentinel llm list
NAME VERSION DEFAULT MODEL API KEY
anthropic 1.0.0 claude-3-5-sonnet-20241022 set
gemini 1.0.0 gemini-1.5-flash unset
ollama 1.0.0 qwen2.5-coder:7b n/a
...

$ sentinel llm doctor --provider gemini
PROVIDER STATUS LATENCY DETAIL
gemini available 142.1ms ok

$ sentinel llm price --provider openai
MODEL INPUT/1k OUTPUT/1k
gpt-4-turbo $0.010000 $0.030000
gpt-4o $0.005000 $0.015000
gpt-4o-mini $0.000150 $0.000600
```

## Config example

```yaml
# sentinel.config.yaml
llm: default_provider: anthropic providers: anthropic: api_key_env: ANTHROPIC_API_KEY models: planner: claude-3-5-sonnet-20241022 analyzer: claude-3-5-haiku-20241022 ollama: host: http://localhost:11434 models: planner: qwen2.5-coder:7b budget: max_usd_per_run: 0.50 max_usd_planner: 0.30 rate_limit: requests_per_minute: 60
```

The existing per-caller blocks (`planner.llm.*`, `analyzer.llm.*`)
remain the fine-grained surface and override `llm.default_provider`
for that caller.

## Error grid

| Code        | Exit | Meaning                                             |
| ----------- | ---- | --------------------------------------------------- |
| `E-LLM-001` | 5    | Missing API key (env var unset).                    |
| `E-LLM-002` | 5    | Model unknown / unreachable.                        |
| `E-LLM-003` | 1    | Per-run cost budget exceeded.                       |
| `E-LLM-004` | 3    | Provider rejected request (4xx other than 401/429). |
| `E-LLM-005` | 3    | Response failed structured-output validation.       |
| `E-LLM-006` | 3    | Provider request timed out.                         |
| `E-LLM-007` | 3    | Provider returned HTTP 429 (rate-limited).          |
| `E-LLM-008` | 3    | Caller-side schema mismatch.                        |
| `E-LLM-009` | 2    | Selected model doesn't support structured output.   |

## Adding a new provider

1. Create `engine/llm/providers/<name>.py`. Subclass `HttpLlmProviderBase`. Override: - `endpoint_url` — the POST URL. - `auth_headers(*, api_key)` — auth headers. - `build_payload(*, request, model)` — request body. - `extract_response_text(body)` — model output as a string. - Optional: `usage_from_response`, `cost_from_response`, `doctor`.
2. Add an entry to `engine/llm/providers/__init__.py::_bootstrap()`.
3. Add a `_PRICING_USD_PER_1K` table if the provider has a known cost surface.
4. Write `tests/unit/llm/providers/test_<name>.py` with `httpx.MockTransport` — happy path, 401, 429, 4xx/5xx, schema validation.
5. Update this page.

## See also

- ADR-0042 — Canonical multi-provider LLM adapter layer.
- ADR-0037 — Provider-agnostic LLM access.
- `engine/llm/protocol.py` — the canonical Protocol.
- `engine/llm/providers/_http_base.py` — shared scaffolding.
- `apps/cli/src/sentinel_cli/commands/llm_cmd.py` — `sentinel llm` CLI.
