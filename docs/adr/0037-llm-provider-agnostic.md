# ADR-0037: Provider-agnostic LLM access through adapters

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #4 asked which LLM providers should be supported
first. The recommended answer was "provider-agnostic through an
adapter interface." The Phase 06 planner (ADR-0011) and Phase 09
analyzer explainer (ADR-0014) both shipped that way: a Protocol
plus two HTTP-only reference adapters (OpenAI, Anthropic) and a
`NullLlmPlanner` / `NullLlmExplainer` default.

This ADR is one of the eight Phase-27 open-question ADRs.

## Decision

**Every LLM-using feature is implemented behind a Python Protocol
with a `Null<X>` default and a small set of HTTP-only reference
adapters.** No vendor SDK is added to the dependency closure. Each
adapter POSTs to the vendor's documented HTTP API via the standard
`httpx` client. Prompts are versioned at
`engine/<module>/llm_prompts/<name>.vN.md` with a `PROMPT_VERSION`
constant in code. Per-run USD spend is bounded by a config knob
(`<module>.llm.max_usd_per_run`); a `BudgetExceededError` falls back
to deterministic output.

The two reference providers are **OpenAI** (Chat Completions API)
and **Anthropic** (Messages API). Additional providers are out-of-tree
plugins; the Protocol contract is stable.

## Consequences

- **Positive:** users pick their provider. Air-gapped users pick the `Null<X>` default and get fully deterministic output. Switching providers is a config change.
- **Positive:** the dependency closure stays small — `httpx` is the only LLM-related runtime dep.
- **Positive:** prompt versioning makes provider behavior changes reproducible and auditable.
- **Negative / trade-off:** new vendor-specific features (e.g. Anthropic's tool use, OpenAI's structured-output mode) require per-adapter work. Acceptable — we keep the cross-cutting Protocol thin and only graduate features that survive review against both.
- **Negative / trade-off:** a generic adapter cannot use the best per-provider primitive when the providers diverge. Accepted — the cost of a "best-of-both" abstraction layer would erase the simplicity win.
- **Follow-up obligations:** every new LLM-using module follows the same Protocol + adapter pattern; default is `Null`; spend is bounded; prompts are versioned.

## Alternatives considered

- **OpenAI-only.** Faster to ship, but locks users into one vendor and makes air-gapped deployment painful.
- **Vendor SDKs.** Adds large transitive dependency trees, slower startup, harder reproducibility. Rejected — the HTTP surface is small enough that the adapters fit in a single Python module each.
- **A central proxy SaaS.** Forces every customer to send target traffic through us. Rejected per ADR-0033.

## References

- our product spec Open Question #4 + recommended answer
- the documentation Planner, §9.5 Analyzer
- our engineering rules
- Related ADRs: ADR-0011 (Planner deterministic vs LLM), ADR-0014 (Analyzer)
