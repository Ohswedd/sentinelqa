# ADR-0023: MCP & agent interface — stdlib JSON-RPC server, twelve sentinel.\* tools, envelope contract

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

Phase 18 lights up the Model Context Protocol (MCP) and agent interface
(PRD §15, §16; CLAUDE.md §15). The goal is for a Claude-Desktop-class
MCP client to connect to a SentinelQA-aware process and call every
PRD §16.1 tool with structured arguments, structured results, and
PRD §15-grade safety guarantees.

Three forces shape the design:

1. **Strict dependency hygiene (CLAUDE.md §35).** The official `mcp`
   Python SDK on PyPI (`mcp >= 1.27`) requires Pydantic ≥ 2.13,
   `starlette`, `uvicorn`, `cryptography`, `cffi`, `pyjwt`, `httpx-sse`,
   `sse-starlette`, and `python-multipart`. The Pydantic bump alone
   ripples through every locked domain model in `engine.domain` and
   every Phase-01..16 schema test. The HTTP stack is for OAuth flows and
   SSE we do not use — we need stdio + (optionally) a local HTTP loop
   for one-machine development. Adding all of that for the tool-call
   surface PRD §16 actually requires is "adding a large framework for a
   small utility" (CLAUDE.md §35).

2. **Determinism + auditability (PRD §6.8, CLAUDE.md §15, §39).** Agent
   responses must be byte-stable across runs so byte-locked golden tests
   and replay-debugging work. The MCP SDK's serialisation passes Pydantic
   model objects through to its writer; we want full control of the wire
   bytes so envelopes are deterministic.

3. **Boundary clarity (CLAUDE.md §7).** The MCP server is a _transport_
   adapter over the Phase-16 SDK. Tools must not duplicate engine logic
   — they translate JSON-RPC arguments into `sentinelqa.Sentinel`
   method calls and translate results back into the agent envelope.

The PRD §16 surface is small: twelve tools, all of which the Phase-16
SDK can already serve. The wire protocol we need to speak is
JSON-RPC 2.0 over NDJSON-framed stdio (the MCP base transport, spec
version `2024-11-05`).

The task file (`plans/phase-18-mcp-agent-interface/01-mcp-server-skeleton.md`)
named the official `mcp` PyPI package as the implementation vehicle.
Per CLAUDE.md §2 authority order (CLAUDE.md > task plans), this ADR
overrides that. The DELIVERABLE — a Claude-Desktop-callable MCP server
exposing twelve sentinel.\* tools — is unchanged.

## Decision

We implement the MCP server inside SentinelQA's own monorepo as a pure
Python package, with **no new runtime dependencies beyond what the SDK
already pulls in** (stdlib + Pydantic 2.10.x + Pyyaml). The package
lives at `packages/mcp-server/` and ships as the distributable
`sentinelqa-mcp` (PyPI name).

### Package layout

```
packages/mcp-server/
  pyproject.toml
  src/sentinelqa_mcp/
    __init__.py            public exports
    __main__.py            python -m sentinelqa_mcp
    protocol.py            JSON-RPC + MCP types
    transport.py           stdio + http transports (asyncio)
    server.py              dispatch, lifecycle, capability negotiation
    envelope.py            AgentEnvelope wrapping every tool result
    errors.py              ToolError + JSON-RPC error codes
    verify_fix.py          verify-fix loop logic
    tools/
      __init__.py          registry, ToolSpec, Tool protocol
      ping.py
      discover.py
      plan.py
      generate_tests.py
      run_tests.py
      audit.py
      security_audit.py
      performance_audit.py
      accessibility_audit.py
      read_report.py
      explain_failure.py
      suggest_fix.py
      verify_fix.py
```

### Wire protocol

- **Base transport:** NDJSON over stdio (one JSON-RPC message per line,
  utf-8, `\n` framed). The MCP "stdio transport" spec calls for exactly
  this; we do not negotiate `Content-Length`-style HTTP-like framing.
- **JSON-RPC version:** 2.0 exactly. Errors use the standard
  `-32700/-32600/-32601/-32602/-32603` codes plus a SentinelQA
  application-error code (`-32001`) carrying the SDK exit code and the
  `to_agent_message()` payload.
- **MCP protocol version:** `2024-11-05` only (declared in
  `initialize`). Newer protocol versions are rejected with a
  `protocol_version_unsupported` error so a future SDK upgrade is an
  explicit change, not a silent drift.
- **Methods implemented:** `initialize`, `notifications/initialized`,
  `tools/list`, `tools/call`, `ping`. `notifications/cancelled` is
  observed (we mark the in-flight tool best-effort cancelled) but
  cooperative cancellation is best-effort per CLAUDE.md §32.
- **`tools/list` shape:** every tool reports `name`, `description`,
  `inputSchema` (Draft 2020-12, generated from a Pydantic args model),
  and a SentinelQA-specific `_meta.read_only` boolean for clients that
  honor read-only hints.
- **`tools/call` shape:** result is `{ "content": [{ "type": "text",
"text": <serialised envelope> }], "isError": <bool>, "_meta": {
"agent_envelope_schema_version": "1" } }`. The serialised envelope is
  the AgentEnvelope defined below; we render it as JSON inside the
  `text` block because the MCP base spec ships _text_, _image_, and
  _resource_ content kinds — not free-form JSON — and clients render
  unknown JSON by stringifying anyway.

### AgentEnvelope (task 18.03)

Every tool — success or failure — returns the same shape:

```json
{
  "schema_version": "1",
  "tool": "sentinel.audit",
  "result": {
    /* tool-specific */
  },
  "errors": [
    /* zero or more error agent-messages */
  ],
  "evidence_refs": [
    /* file paths relative to the run dir */
  ]
}
```

- `schema_version` is `AGENT_ENVELOPE_SCHEMA_VERSION = "1"`. Bumps
  follow the same deprecation policy as the SDK (ADR-0021).
- `result` is `null` only when `errors` is non-empty (an error envelope
  carries no result).
- `errors[]` items are exactly the `SentinelError.to_agent_message()`
  shape — `code`, `exit_code`, `message`, `suggested_fix`,
  `technical_context`, redacted by the engine's redactor (CLAUDE.md
  §33).
- `evidence_refs[]` is a flat list of relative paths beneath the run
  directory (`run.json`, `findings.json`, `traces/...`, etc.) that the
  caller can fetch via subsequent `sentinel.read_report` calls.

The envelope shape is locked by a Draft 2020-12 schema at
`packages/shared-schema/agent-envelope.schema.json` and pinned by a
byte-locked golden test under `tests/golden/mcp/`.

### Safety contract (CLAUDE.md §6, §15, PRD §15)

- Every tool that takes a `url` argument runs `SafetyPolicy.enforce`
  _inside_ the tool, before any SDK call. A blocked target produces an
  envelope with `result=null`, a single error agent-message carrying
  `code="UNSAFE_TARGET"` / `exit_code=4`, and `evidence_refs=[]`.
- The MCP server never enables `security.mode=authorized_destructive`
  on the caller's behalf. Tools that wrap destructive surfaces
  (`sentinel.security_audit` covers safe checks only by default) refuse
  the destructive path unless the call explicitly supplies
  `proof_of_authorization` and the loaded config opts in. There is no
  CLI flag and no MCP argument that disables the safety boundary.
- Stdio transport logs MUST go to stderr only — stdout is reserved for
  MCP wire bytes. The package configures the engine logger to stderr
  for the lifetime of the server.
- Every URL/target string the server emits is run through
  `engine.policy.redaction.redact` before being placed on the wire.

### `sentinel.verify_fix` (task 18.04)

`sentinel.verify_fix` is the only tool whose contract is **broader than
its underlying SDK method**. The SDK's `Sentinel.verify_fix` is a
Phase-20 (Healer) placeholder that raises `NotImplementedError`. The
MCP tool instead implements the _agent-observable_ loop without
applying any code changes (the agent is the one editing files):

1. Resolve the named `run_id` and its impacted spec set (intersected
   with the diff-aware selector if `diff_range` is provided).
2. Re-invoke `Sentinel.audit(modules=affected, ...)` against the
   _current working tree_ — i.e. whatever the agent just wrote to
   disk.
3. Diff the new `findings.json` against the prior run's
   `findings.json`: same-`finding.fingerprint` items are "unchanged",
   removed items are "fixed", new items are "regressions".
4. Return a typed `VerifyFixResult` with a four-valued decision:
   - `fix_verified` — original target finding is gone AND no new
     findings.
   - `partial` — original target finding is gone OR resolved, but
     some other prior finding has reappeared / lingered.
   - `regressed` — original target finding is still present AND at
     least one new finding exists.
   - `still_failing` — original target finding is still present and no
     new findings appeared.

The Healer's own apply-fix logic (CLAUDE.md §23) lands in Phase 20;
this ADR commits Phase 18 only to the verification loop.

### `sentinel mcp` CLI (task 18.05)

The Phase-02 stub is replaced. Options:

- `--stdio` (default) — speak the stdio transport on this process.
- `--http <PORT>` — bind to `127.0.0.1:<PORT>` only; refuses any
  non-loopback bind. This is a local-development convenience; production
  agent loops use stdio.
- `--config <PATH>` — override the config path the tools load.
- `--log-level <LEVEL>` — engine log level, written to stderr.

Exit codes follow the canonical grid (0 success, 2 config error, 4
unsafe target rejected, 7 internal error). The HTTP variant binds _only_
to loopback; any other bind attempt is refused with exit 4.

### Tests (task 18.06)

- `tests/integration/mcp/test_server_skeleton.py` — boot the server
  in-process, send `initialize` → `tools/list` → `ping`, assert
  responses.
- `tests/integration/mcp/test_tools_contract.py` — one parametrised
  test per tool: arg-schema rejects junk, success path returns a valid
  envelope, URL tools enforce safety policy.
- `tests/golden/mcp/test_tool_envelopes.py` — byte-locked envelope
  goldens for `ping`, `audit (success)`, `audit (unsafe)`,
  `verify_fix (fix_verified)`.
- `tests/integration/mcp/test_verify_fix_loop.py` — fixture loop:
  apply a known "fix" to a synthetic run, expect `fix_verified`.
- `tests/integration/cli/test_mcp.py` — `sentinel mcp` boots,
  `--http <bad>` refuses non-loopback, `--log-level` flows through.
- `tests/security/test_mcp_safety.py` — AST-level guard that every
  tool with a `url` parameter calls `SafetyPolicy().enforce` before any
  SDK call (mirrors `tests/security/test_module_calls_policy.py`).

Coverage floor for `packages/mcp-server/src/sentinelqa_mcp/`: 85 %
(matches Phase 18 task 06).

## Consequences

- **Positive:**
  - Zero new runtime dependencies. The Pydantic 2.10.x pin and the
    locked SDK / domain models stay byte-identical.
  - Wire bytes are SentinelQA's, not a vendor library's. Byte-locked
    goldens and replay debugging stay deterministic across upgrades.
  - The transport is a thin adapter (~400 LoC) we can fully test in
    process. No subprocess fan-out for tests, no flakiness from
    starlette / uvicorn startup races.
  - Local HTTP debug loop is loopback-only — there is no accidental
    public exposure path.
- **Negative / trade-off:**
  - We track the MCP spec ourselves. New protocol versions require a
    deliberate update (we reject unknown versions, which is the safe
    default for an audit tool). The transport adapter is wrapped behind
    a `MCPTransport` protocol so swapping it for the official SDK in a
    later phase is a one-class change if our hand-rolled implementation
    proves limiting.
  - We do not gain MCP SDK's built-in OAuth flow, SSE streaming, or
    the experimental `roots`/`resources`/`prompts` surfaces. We do not
    need any of those for PRD §16. If we ever do, that lands as a
    separate ADR.
- **Follow-up obligations:**
  - Phase 20 (Healer) supplies `Sentinel.verify_fix`'s actual
    apply-fix logic. The Phase-18 MCP `sentinel.verify_fix` already
    works without it — the agent applies fixes, the MCP tool verifies.
    When Phase 20 lands, the MCP tool grows an opt-in `apply` mode that
    delegates to the Healer; the existing decision matrix is preserved.
  - Phase 24 (Plugin Architecture) may expose a way for third-party
    audit modules to register MCP tools alongside the built-ins. The
    `ToolRegistry` already supports late registration — no schema
    bump is required.
  - Phase 27 (Docs) ships the Claude Desktop walkthrough as a doc page;
    `docs/user/mcp.md` is the Phase-18 stub.

## Alternatives considered

- **Adopt the official `mcp` PyPI SDK.** Rejected because it forces
  Pydantic 2.10.x → 2.13.x across the whole codebase and pulls
  starlette/uvicorn/cryptography for OAuth + SSE capabilities we do not
  need (CLAUDE.md §35). The deliverable — a Claude-Desktop-callable MCP
  server — does not require the SDK; it requires conformance to the
  base JSON-RPC-over-stdio transport, which is a small surface.
- **Implement the server in TypeScript using `@modelcontextprotocol/sdk`.**
  Rejected because the engine and SDK are Python, every PRD §16 tool
  needs to call the Python SDK, and a JS server would either fork a
  Python subprocess per call (high latency, fragile redaction) or
  marshal everything through stdio twice. CLAUDE.md §8 owns runtime
  partitioning: TS owns Playwright; Python owns orchestration.
- **Bolt the MCP surface onto the Phase-16 SDK directly.** Rejected
  because the SDK is the _embedded_ surface (PRD §14). Agents talking
  MCP need a separate process; mixing transport into the SDK violates
  CLAUDE.md §7 (layered architecture) and would couple the SDK release
  cadence to MCP protocol updates.
- **Lift sentinel envelopes verbatim from the Phase-16 agent message
  stream.** Rejected because the existing stream is per-event
  (`run_summary`, `finding`, `blocker_summary`, `next_actions`) — useful
  for an audit transcript but the wrong shape for a per-tool-call
  response. The envelope wraps a _result_; it embeds the agent-message
  stream as a value (in `result.agent_messages` for `audit`).

## References

- PRD section(s): PRD §15 (Agent rules), §16 (MCP / LLM Tool Interface),
  §31 open question 5 (yes, day-one MCP).
- CLAUDE.md rule(s): CLAUDE.md §6 (Safety boundary), §15 (Agent
  Interface Rules), §35 (Dependency Rules).
- External: MCP base spec
  (https://spec.modelcontextprotocol.io/specification/2024-11-05/),
  JSON-RPC 2.0 (https://www.jsonrpc.org/specification).
- Related ADRs: ADR-0006 (Safety policy), ADR-0007 (Run lifecycle),
  ADR-0014 (Analyzer — `explain_failure` underlying logic), ADR-0021
  (Public SDK surface — `to_agent_message()`), ADR-0022 (CI integration
  — diff-aware selector reused by `verify_fix`).
