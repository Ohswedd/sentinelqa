# ADR-0033: Cloud boundary — no SentinelQA cloud in the release

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our engineering rules"Cloud boundary" as a required ADR trigger. the documentation
§7 (Scope), §11 (Architecture), §24 (release Definition), §31 (Open
Questions #3), and §32 (Recommended Build Order) all assume the release
ships as an open-source CLI / SDK / MCP server running entirely on
the user's machine or in their CI. The product strategy is to earn
trust with a self-hosted core before any hosted offering.

The phase plan (–17 collectively constitute the release, per §5) deliberately defers any cloud orchestrator,
hosted dashboard, multi-tenant database, or shared queue. Integrations
that touch third-party SaaS ( — BrowserStack, Sauce Labs,
Slack, GitHub, Jira, Linear) are explicitly user-driven adapters
with the user's own credentials, not a SentinelQA-hosted bridge.

This ADR records the boundary so future contributors know which
features are deliberately out of scope vs. deferred. Adding a hosted
component without superseding this ADR is a process error.

## Decision

**No SentinelQA-hosted service ships in the release.** Concretely, the
following are out of scope for any phase numbered ≤ 29:

- A SentinelQA-hosted dashboard, multi-tenant database, or auth system.
- A SentinelQA-managed test orchestrator (queues, sharding workers, scheduling).
- A SentinelQA-hosted artifact store (run.json, traces, screenshots, videos).
- Centralised telemetry — see our engineering rules(no telemetry by default; any future telemetry is opt-in, documented, redacted, disableable).
- A hosted plugin marketplace or registry.
- A SentinelQA-managed LLM proxy or shared API key.

All cloud-shaped interactions in the release are **user-owned adapters**:

- `RunnerPlugin` instances (BrowserStack, Sauce Labs) use the user's credentials, post to the vendor's API directly, no SentinelQA intermediary (ADR-0030).
- Slack / GitHub / GitLab / Jira / Linear posters use the user's webhook / token, posted from the user's machine or CI runner.
- LLM adapters (planner, analyzer explainer) are configured per-user and posted directly from the user's process to the chosen vendor (ADR-0011, ADR-0014).

## Consequences

- **Positive:** Zero attack surface on SentinelQA-managed infrastructure. No data residency or multi-tenant isolation questions to answer. Trust model is the user's: they bring the credentials, they hold the data, the artifacts never leave their disk.
- **Positive:** Distribution is simple — pip install, pnpm install, docker run. No signup. No "request access" gate.
- **Positive:** Open-source positioning is honest. The CLI is the product; nothing important is gated behind a closed cloud.
- **Negative / trade-off:** Some capabilities are harder to deliver without a hosted backend — cross-team historical trend lines, cross-org plugin discovery, comparative benchmarks. These wait.
- **Negative / trade-off:** Self-hosted ops burden falls on the user (CI minutes, disk for `.sentinel/runs/`, baseline storage). The HTML report's trend overlay reads from the local `.sentinel/runs/` directory; sharing trends across machines is the user's problem.
- **Follow-up obligations:** Any post-release proposal for a hosted component must supersede this ADR (write a new ADR; reference this one as `Superseded by ADR-NNNN`) before any implementation lands.

## Alternatives considered

- **Ship a thin hosted dashboard alongside the CLI from day one.** Rejected: doubles the scope (auth, billing, hosting, security posture, multi-tenancy) before we have any users on the CLI, and burns trust the open-source positioning depends on.
- **Hosted LLM proxy to abstract over OpenAI/Anthropic.** Rejected: forces every user to send their target's traffic through us. Wins no real benefit over our existing typed adapter Protocol.
- **Hosted artifact store for cross-team report sharing.** Rejected: same trust + scope concern as the dashboard. Users can publish `.sentinel/runs/<id>/report.html` from their own CI artifact store if they want sharing.

## References

- our product spec Scope
- our product spec Architecture
- our product spec release Definition
- our product spec Open Questions #3 (Should cloud be delayed until open-source adoption exists?)
- our product spec Recommended Build Order
- our engineering rules(cloud boundary trigger)
- our engineering rules
- Related ADRs: ADR-0030 (Integrations), ADR-0036 (Cloud delayed until CLI traction)
