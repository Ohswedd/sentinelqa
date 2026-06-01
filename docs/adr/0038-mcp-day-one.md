# ADR-0038: Ship an MCP server on day one

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #5 asked whether the product should expose MCP
from day one. The recommended answer was "yes, at least a basic MCP
server." Phase 18 shipped a full MCP server (ADR-0023) speaking
JSON-RPC 2.0 over NDJSON-framed stdio at protocol `2024-11-05`, with
twelve the documentation tools + a `sentinel.ping` health check.

This ADR is one of the eight Phase-27 open-question ADRs.

## Decision

**Ship a first-class MCP server in the MVP, not after.** The server
is part of the same package set as the CLI and SDK (no separate
distribution). The default transport is stdio; the alternate
transport is loopback-only HTTP that refuses any non-loopback bind
(exit 4). The server uses no third-party MCP runtime — only the
stdlib + `pydantic` + the existing `sentinelqa` SDK.

Tool surface is locked at the the documentation twelve + `sentinel.ping`.
Every URL-bearing tool runs `SafetyPolicy.enforce` before any SDK
call; an AST guard test enforces this on every CI pass.

## Consequences

- **Positive:** SentinelQA is usable by Claude Desktop (and any MCP-aware agent) the day it ships. The `examples/mcp-claude-desktop/` config is a one-step setup.
- **Positive:** the agent-facing surface is the same one a human user would use through the SDK — same `Sentinel.audit()` call, same envelope shape. No second contract to maintain.
- **Positive:** zero new runtime dependencies. The MCP server reuses the existing typed models and the same redaction pipeline.
- **Negative / trade-off:** the MCP protocol is still evolving; the pinned `2024-11-05` revision will need maintenance. Acceptable — the surface is small and the wire-envelope versioning gives us upgrade room (`AgentEnvelope.schema_version`).
- **Negative / trade-off:** every URL-bearing tool now has two enforcement layers (the SDK's `SafetyPolicy` and the MCP wrapper's `enforce_url`). Intentional belt-and-suspenders for the safety boundary.
- **Follow-up obligations:** the AST safety guard (`tests/security/test_mcp_safety.py`) stays green on every CI pass; any new MCP tool runs `SafetyPolicy.enforce` and surfaces unsafe targets as envelope errors.

## Alternatives considered

- **No MCP in the MVP.** Rejected — agent-facing tooling is a core part of the SentinelQA value story (release-confidence engine for LLM-built apps). Shipping the CLI without MCP would leave the agent half of the audience unaddressed.
- **MCP-only (no CLI).** Rejected — humans audit too. The CLI is the long-term contract.
- **Use a hosted MCP gateway.** Rejected per ADR-0033.

## References

- our product spec Open Question #5 + recommended answer
- our product spec MCP Tools
- Related ADRs: ADR-0023 (MCP & agent interface)
