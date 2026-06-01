# ADR-0011: Planner is deterministic-first; LLM adapter is opt-in behind a locked, versioned prompt

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

builds the Planner module (the documentation): given a `DiscoveryGraph` + `RiskMap`, emit a `TestPlan` that names every flow + test case the runner will execute. The PRD's open questions (§31) explicitly asks whether the planner should be LLM-driven; the documentation already declares the principle that LLMs plan/explain while deterministic runners execute.

Constraints we must honor:

- **Determinism (the documentation, CLAUDE §19)** — same inputs must produce the same plan modulo IDs. A hosted LLM cannot guarantee that.
- **Safety (CLAUDE §6, §32, §41)** — no source-code upload, no PII in payloads, no destructive flows ever, no production credentials.
- **No fake completion (CLAUDE §37)** — every planned test case must be reproducible from the graph alone, regardless of LLM availability.
- **CI must work air-gapped** — CI runs without provider API keys; planning cannot become a hard dependency on a vendor's uptime.
- **Vendor neutrality (our product spec open question 4)** — SentinelQA must not be locked into a single LLM provider.

Two pressures pull on this design:

1. Planner _quality_ improves with an LLM that knows real-world flow patterns the deterministic rules miss (magic-link login, session-expiry probes, multi-tenant boundaries).
2. Planner _trust_ requires every shipped flow to be auditable, reproducible, and run-anywhere.

## Decision

The planner is **deterministic by default; an LLM adapter can augment — never replace — the deterministic output, behind a feature flag**.

Concretely:

1. The deterministic core (`engine.planner.core.DeterministicPlanner`) is the only path required to produce a plan. Without LLM credentials and with `planner.llm.enabled=false` (the default), planning works end-to-end.
2. The LLM adapter is implemented as a `Protocol` (`engine.planner.llm_adapter.LlmPlanner`), with a `NullLlmPlanner` as the default no-op. Two providers ship: `openai_planner.py` and `anthropic_planner.py`. Both speak HTTP+JSON directly via `httpx`, never via vendor SDKs, so SentinelQA stays decoupled from provider release cadences.
3. The provider system prompt lives in a versioned file: `engine/planner/llm_prompts/planner.v1.md`. Any prompt change requires a new ADR plus a `planner.vN.md` bump. The version is exported as `PROMPT_VERSION` so consumers can detect drift.
4. The graph payload sent to the provider is built by `build_graph_summary` from `engine.planner.llm_adapter` — route paths, auth-required booleans, counts, existing flow names. No URLs with query strings, no form field values, no headers, no cookies, no env-var values.
5. LLM proposals are re-parsed through Pydantic (`_ProposalEnvelope`). Malformed proposals are dropped silently with the request still recorded for budget accounting. Proposals are rejected when the proposed `target_route_path` is not in the graph or when the proposed name collides with an existing deterministic flow.
6. Each accepted proposal becomes a `Flow` with `source="llm"`, `extractor="llm.v<PROMPT_VERSION>"`, and at least the `"llm"` tag. The runner (+) and scoring can therefore distinguish deterministic vs. LLM-sourced flows.
7. **Hard per-run USD budget** is enforced (`planner.llm.max_usd_per_run`, default 0.50). When the projected cost of the next call would exceed the budget, the adapter raises `BudgetExceededError` and the CLI falls back to deterministic-only with an audit-log entry. Token-cost is estimated from response usage when present; conservative chars/4 heuristic when not.
8. Provider credentials are read **by env-var name** from the config (`planner.llm.api_key_env`), never inlined. This matches the existing `AuthConfig` rule (CLAUDE §33).
9. Every LLM invocation writes one structured `plan.llm.usage` line to `audit.log` with provider, request count, tokens, and cost — so a security reviewer can prove what was sent to whom.
10. CI default: `planner.llm.enabled=false`. Even if a key is set, CI must opt in explicitly per-run.

## Consequences

- **Positive:** - Planning is fully reproducible without an LLM. Tests, CI, and golden fixtures all work air-gapped. - Adding a third provider is a single subclass of `HttpLlmProviderBase`. - The locked, versioned prompt makes prompt-engineering changes reviewable as code — they show up in `git diff` as `planner.vN.md` changes plus an ADR. - The `source` field on `Flow` lets downstream modules treat LLM-proposed flows differently (e.g., scoring weights them lower, the healer requires human review). - The budget cap makes "LLM planner ran wild" impossible by construction.

- **Negative / trade-off:** - The cost estimator is conservative (chars/4) and may over-refuse under exotic prompts. We accept that — refusing is the safe failure mode. - The HTTP-direct integration means we don't get vendor SDK ergonomics (streaming, retries with jitter, structured-output mode where the SDK provides one). We deemed this acceptable because the planner is a single short request per run. - Two providers (OpenAI + Anthropic) ship now, but vendors that don't speak chat-message HTTP+JSON (Bedrock, Vertex, local Ollama) need their own subclasses later.

- **Follow-up obligations:** - The MCP agent interface (`sentinel.plan_with_llm`) will route through this same adapter — no parallel LLM path. - The docs site documents the locked prompt verbatim. - The final safety audit re-reads `planner.v1.md` to confirm no flow-class has crept in that violates CLAUDE §6 (stealth, evasion, etc.). - The redaction layer (`engine.policy.redaction`) is the source of truth for what must NOT appear in the LLM payload; future changes to `build_graph_summary` MUST round-trip through redaction tests.

## Alternatives considered

- **LLM-first planner.** Every flow comes from the LLM; deterministic rules cover only what the LLM missed. Rejected because it makes planning non-reproducible by default and breaks CI when the provider is down or rate-limited.
- **Vendor SDKs (openai, anthropic) as dependencies.** Cleaner ergonomics, but pins SentinelQA to vendor release cadences and would force every consumer (including air-gapped users) to install SDKs they may never call.
- **A single "generic" OpenAI-compatible adapter.** Some local LLMs expose an OpenAI-compatible endpoint; one adapter could cover Together, Groq, vLLM, etc. Rejected for the release — the providers we care about (OpenAI's first-party endpoint + Anthropic's Messages API) have meaningfully different request/response shapes; subclassing keeps each adapter readable. The generic adapter can land as a third subclass later without breaking the Protocol.
- **Hand-write the system prompt inline in `openai_planner.py` / `anthropic_planner.py`.** Easier to ship, but every prompt edit becomes a Python diff in a provider file, not an auditable prompt change. The locked-file approach makes prompt-versioning explicit.
- **Charge per-token instead of per-USD.** Token counts are vendor-specific and shift when models change; USD is the only unit that maps to actual cost. Estimating cost from a per-1k price table is good-enough for an "is this still safe?" gate.

## References

- PRD section(s): the documentation (Principles), the documentation (Planner), our product spec (TypeScript Runtime — separate from this ADR), our product spec open question 4 (provider-agnostic).
- our engineering rules rule(s): our engineering rules(Safety boundary), §15 (Agent interface), §19 (Code quality), §32 (Error handling), §33 (Logging and secrets), §37 (No placeholder completion), §41 (Privacy and telemetry).
- Related ADRs: ADR-0005 (Config schema), ADR-0006 (Safety policy), ADR-0008 (Report schemas), ADR-0010 (Discovery release HTTP-first).
- External: OpenAI Chat Completions API; Anthropic Messages API.
