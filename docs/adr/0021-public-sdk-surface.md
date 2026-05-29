# ADR-0021: Public SDK surface

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

PRD §14 makes the Python SDK a first-class delivery target: a typed,
agent-friendly facade callers use to embed SentinelQA in scripts and
LLM-agent flows. CLAUDE.md §14 makes the SDK's public contract binding —
"any documented SDK behavior is public contract and requires tests."
CLAUDE.md §40 binds that contract to a deprecation policy: breaking
changes require a deprecation window and an ADR. We need a single,
auditable answer to "what does `from sentinelqa import …` promise?" so
future phases (17 CI, 18 MCP, 20 Healer) extend the surface without
silently changing it.

PRD §14.3 lists the contract by name: `Sentinel`, `AuditResult`,
`Finding`, `Evidence`, `TestPlan`, `Flow`, `RiskMap`, `QualityGate`,
`Policy`, `ModuleResult`, `RepairSuggestion`. Phase 01 already shipped
typed exceptions with `to_agent_message()` and a stable code/exit-code
contract. The remaining decision is how to expose those types as a
versioned, snapshot-locked surface.

## Decision

We lock the public SDK surface to three importable modules and gate
changes with an on-disk snapshot.

**Public modules** (and only these) are part of the contract:

- `sentinelqa` — facade + result models + schema-version constants.
- `sentinelqa.errors` — every public exception, plus the `from_dict()`
  reconstructor for round-tripping a redacted agent message back into
  a typed exception.
- `sentinelqa.agent` — agent-message helpers: `finding_to_agent_message`,
  `repair_suggestion_to_agent_message`, `audit_result_to_agent_messages`,
  and `format(messages, *, format='ndjson'|'jsonl'|'list')` for piping
  to an LLM context.

Everything else — anything in `sentinelqa._internal/`, anything whose
name starts with `_`, anything not enumerated in those modules'
`__all__` — is **not** public. External code that imports it is
explicitly on its own.

**Surface gate.** `packages/python-sdk/api-snapshot.json` records the
public surface as JSON: for every name in every public module's
`__all__`, we capture kind (`class` / `function` / `constant`) plus, for
classes, the SDK-defined `own_attributes` set and any Pydantic
`model_fields` (the latter is the wire shape — adding a required field
is breaking). `tests/unit/sdk/test_api_snapshot.py` diffs the snapshot
against the live surface on every CI run. A drift fails the test until
the snapshot is regenerated via `make sdk-api-snapshot` AND the
accompanying PR carries an ADR + minor-version bump per
`packages/python-sdk/__deprecation_policy.md`.

**Agent messages.** Every public exception, every `Finding`, every
`RepairSuggestion`, and the top-level `AuditResult` expose a stable
agent-message dict via `to_agent_message()` (or
`to_agent_messages()` for the aggregate). Shapes are versioned by
`AGENT_MESSAGE_SCHEMA_VERSION` (orthogonal to the per-artifact
`FINDINGS_SCHEMA_VERSION` / `RUN_SCHEMA_VERSION`); redaction is applied
at the SDK boundary so dicts are safe to ship straight to an LLM.

**Sync + async parity.** Every long-running method (`discover`,
`plan`, `generate_tests`, `audit`, `run_plan`, `report`, `verify_fix`)
has an `async_<name>` counterpart. The synchronous form is implemented
as `asyncio.run(self.async_<name>(...))` — exactly one implementation,
no behavioural drift.

**Deferred capability.** `verify_fix` raises `NotImplementedError`
until the Healer (Phase 20) ships. The name is part of the surface so
callers can write against it today; the implementation is the only
piece deferred, and it is tracked under Phase 20, not as deferred
scope in Phase 16 (CLAUDE.md §37 — `NotImplementedError` is allowed
when concrete adapters are expected).

## Consequences

- **Positive:**

  - One auditable file (`api-snapshot.json`) is the contract. Any
    drift between code and contract is a test failure, not a
    silent regression.
  - `from sentinelqa import …` works the way PRD §14.1 and §14.2
    promise; the examples reproduce verbatim in
    `tests/integration/sdk/test_prd_examples.py`.
  - Agent messages round-trip: every public exception goes
    `error -> dict -> error` losslessly, every finding has a stable
    shape, and `sentinelqa.agent.format(...)` produces deterministic
    NDJSON / JSONL / list serializations.
  - The SDK is lazy-loaded: `import sentinelqa` stays under the 200 ms
    target (measured: ~80 ms on the dev workstation) because heavy
    submodules (orchestrator, planner, discovery, generator, runner,
    reporter) are imported only when the matching facade method is
    called.

- **Negative / trade-off:**

  - The snapshot is one more file to update when the surface
    deliberately grows. The procedure is documented in
    `__deprecation_policy.md`; CI's failure message names the script
    (`make sdk-api-snapshot`) so the fix is one command.
  - Internal helpers under `sentinelqa._internal/` are not stable;
    advanced users who reach past the public surface (e.g. to swap
    the orchestrator) take on their own breakage risk. This is the
    intended trade-off — the alternative (making everything public)
    would lock in implementation details we will want to evolve.
  - `verify_fix` raises `NotImplementedError` today. Documented in
    PRD §14.3 and the docstring; the alternative (omit it) would
    force a breaking change when Phase 20 lands.

- **Follow-up obligations:**
  - Phase 18 (MCP) reuses the same agent-message shapes for its
    `sentinel.*` tools. The MCP server consumes
    `to_agent_message()` outputs directly; if the dict shape changes,
    the MCP wire format changes with it (bump the schema version,
    update the snapshot, write an ADR).
  - Phase 20 (Healer) implements `verify_fix`. When it does, the
    implementation MUST keep the existing signature
    (`(run_id: str, suggestion: RepairSuggestion) -> AuditResult`)
    or ship the deprecation window per the policy file.
  - Phase 17 (CI) reuses the SDK in the GitHub Action. The action
    pins a snapshot-version-compatible SDK version range.

## Alternatives considered

- **Expose everything via `from sentinelqa import *`.** Rejected: it
  pulls heavy modules at import time (busts the 200 ms target),
  surfaces internal helpers as accidentally-public, and pins us to
  the engine's internal shape forever.
- **Snapshot member lists by walking `getattr(obj, name)` for every
  inherited attribute.** Rejected: noisy. Pydantic boilerplate
  (`model_dump`, `parse_obj`, …) and Exception bookkeeping would
  dominate the snapshot. Drift in those is not our contract; tracking
  only SDK-defined `own_attributes` keeps the gate focused on
  intentional changes.
- **No snapshot; rely on docstrings + tests.** Rejected: docstrings
  drift silently and tests written today only catch additions, not
  silent removals. The snapshot is the single source of truth and
  catches both directions of drift.
- **Use semver hashed schemas (signed artifacts) for the wire
  contract.** Rejected as premature for a pre-1.0 SDK; revisit when
  the SDK reaches 1.0 (CLAUDE.md §40).

## References

- PRD §14 — Python SDK Specification.
- PRD §40 — Versioning.
- CLAUDE.md §14 — SDK Rules.
- CLAUDE.md §15 — Agent Interface Rules.
- CLAUDE.md §32 — Error Handling.
- CLAUDE.md §40 — Versioning and Release Rules.
- Related ADRs: ADR-0005 (Config schema), ADR-0008 (Report schemas),
  ADR-0019 (Quality scoring) — all establish stable wire formats the
  SDK re-exports.
- Companion docs: `packages/python-sdk/__deprecation_policy.md`.
