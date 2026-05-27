# Phase 16 — Python SDK

## Objective

Implement the **Python SDK** (PRD §14, §32): first-class typed API for embedding SentinelQA in scripts and AI-agent flows. Stable public contract; async support; structured agent messages; clear error classes.

## PRD / CLAUDE.md references

- PRD §14 SDK, §32 Recommended Build Order (item 11).
- CLAUDE.md §14 SDK rules, §15 Agent interface, §19 Code quality.

## Sub-phases & tasks

1. `01-sentinel-class.md` — `Sentinel` facade with sync + async APIs.
2. `02-models.md` — Surface only domain models intended as public.
3. `03-agent-messages.md` — `to_agent_message()` returns; SDK helpers for agent flows.
4. `04-async-support.md` — Async variants for long-running operations.
5. `05-error-classes.md` — Public errors; doc them.
6. `06-public-api-discipline.md` — `__all__`, deprecation policy, stable schema versions.
7. `07-tests.md` — sweep including importability.

## Definition of Done

- `from sentinelqa import Sentinel, AuditResult, Finding, ...` works.
- Sync and async APIs verified against fixture.
- Agent-message round-trips for every public exception and every finding.
- ADR-0015 (Public SDK surface) committed.

## Phase Gate Review

- [ ] Public API list locked.
- [ ] Async tests green.
- [ ] No internal types leaking through public exports.
- [ ] Docs reference cards exist for every public class.
- [ ] `STATUS.md` updated.
