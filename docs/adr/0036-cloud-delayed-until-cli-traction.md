# ADR-0036: Cloud is delayed until the CLI earns adoption

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #3 asked whether a SentinelQA-hosted cloud
should be delayed until the open-source CLI has adoption. The
recommended answer was "yes, delay cloud until CLI has traction."

This ADR pairs with ADR-0033 (Cloud boundary) — that ADR records the
boundary itself; this ADR records the _temporal_ commitment: we will
not start building a hosted component during release phases (00–29), and
any post-release cloud work waits on demonstrated CLI adoption.

## Decision

**No SentinelQA-hosted cloud component starts before the CLI has
documented adoption.** Concretely:

- –29 ship only the local CLI, SDK, MCP server, plugin architecture, and user-driven integration adapters.
- Any cloud proposal post-release must demonstrate a real need from shipping users — installs, GitHub Action usage, plugin downloads, documented feature requests — before the design work starts.
- Cloud-shaped capabilities that can be modeled as user-owned adapters (ADR-0030) are preferred indefinitely.

## Consequences

- **Positive:** focus stays on making the core engine excellent — better discovery, better generator, better healer, better LLM-Code audits. The differentiator the the documentation claims (release-confidence engine for LLM-built apps) is a CLI story first.
- **Positive:** zero burn on hosting, security posture, multi-tenancy during the trust-building phase.
- **Negative / trade-off:** features that are easier with a backend (cross-machine trends, shared baselines, team analytics) wait. Users who need them today integrate via their own CI artifact store.
- **Follow-up obligations:** (Final Hardening) revisits this ADR. If demand has materialised, the next product cycle writes a new ADR superseding ADR-0033 + this one. Otherwise this ADR stays Accepted and the cloud waits another cycle.

## Alternatives considered

- **Build a hosted dashboard in parallel with the CLI.** Rejected — doubles scope, risks the open-source positioning, and there is no demonstrated demand yet. Same reasoning as ADR-0033.
- **Hosted artifact storage from day one.** Rejected — easy to retro-fit later; not worth the cost now.

## References

- our product spec Open Question #3 + recommended answer
- our product spec Scope
- our product spec Recommended Build Order
- Related ADRs: ADR-0033 (Cloud boundary)
