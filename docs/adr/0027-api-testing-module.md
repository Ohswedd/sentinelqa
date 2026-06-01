# ADR-0027: API testing module — Python-driven httpx with hard payload caps and dedup vs perf

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

the documentation names API testing as one of the release-confidence inputs:
OpenAPI / GraphQL contract validation, negative cases, auth tests,
latency budgets, pagination + uniform error shape, and backward
compatibility checks. our engineering rules:
**no aggressive fuzzing against unauthorized targets**, and a
"safe-payload-only" posture by default. The phase scope spans seven
distinct check kinds plus a CLI entry point; the question is which
runtime owns each one and how the safety boundary is enforced at
multiple layers so a single bug cannot turn the module into a fuzzer.

Three structural decisions framed the implementation:

1. **Runtime ownership.** The module talks HTTP to the target rather than driving a browser, so Python (with `httpx`) is the obvious home. The TS runtime is reserved for the Playwright-driven modules (functional, a11y, perf, visual). Putting the API checks in Python keeps them unit-testable with `httpx.MockTransport` and avoids a second inter-runtime contract just for HTTP probes.
2. **Schema validation library.** OpenAPI specs are validated at load time with `openapi-spec-validator==0.7.1` (already a project dependency from discovery). Per-response schema validation uses `jsonschema==4.23.0` against the OpenAPI Schema Object sub-tree. OpenAPI 3.0 Schema Objects are a near-superset of JSON Schema Draft 7; for release we treat unsupported keywords as advisory. GraphQL parsing uses `graphql-core==3.2.5` for SDL build + type inspection.
3. **How the no-fuzz boundary is enforced.** the engineering guidelines— inside individual check runners (each one bounds its own variants) or at the HTTP boundary (one cap, regardless of caller intent). The decision is **both**, because either alone is fragile.

## Decision

We chose:

1. **Python-owned, `httpx`-driven module.** `modules/api/` is a pure Python package. Every check is a function of `(httpx.Client,
OpenApiDocument | GraphqlSchema, RootConfig)`, returning a typed `ApiCheckResult`. The module subclasses `SentinelModule` ( contract) and emits per-check artifacts under `<run-dir>/api/`.

2. **Layered no-fuzz guard.** - Config-level: `api.negative_max_payload_kb` is clamped at the Pydantic schema layer to `[1, 64]` KB; `api.negative_max_variants_per_endpoint` is clamped at `[1, 16]`. A user cannot widen these in YAML. - I/O-level: `modules.api.http_client.safe_request` enforces an absolute `ABSOLUTE_MAX_REQUEST_BYTES = 64 KB` cap independent of config. Any check that constructs an oversized body fails with `RequestTooLargeError` _before_ the request is issued. - Variant-level: the negative check enumerates a small, fixed variant catalogue (missing-required, wrong-type, out-of-range, oversized-string). It does not iterate randomly or call into a fuzz library. - CLI-level: no `--aggressive`, `--fuzz`, `--brute`, `--stress`, `--unbounded`, or `--no-rate-limit` flag exists on `sentinel api`. - Test-level: `tests/security/test_api_no_aggressive_flags.py` greps `modules/api/` + `apps/cli/.../api_cmd.py` for forbidden literals and introspects the CLI for forbidden patterns.

3. **Latency dedup with perf.** The perf module already enforces `performance.budgets.api_p95_ms` for every sampled endpoint via category `perf/api_latency`. To avoid duplicate findings (the documentation + plan ), the API module's latency check returns `skipped=True` with `skip_reason` naming the perf module's category and budget value. Operators can read the skip reason and trace exactly where the budget is enforced.

4. **Backward-compat snapshot location.** Each run writes `<run-dir>/api/api-schema.json` capturing an `ApiSchemaSnapshot` derived from the loaded OpenAPI / GraphQL doc. The check resolves the prior snapshot via either `--diff-since <run-id>` (explicit CLI flag) or the alphabetically last sibling run-dir under `.sentinel/runs/`. The snapshot intentionally omits descriptions, summaries, and examples — only structural fields are diff'd.

5. **Subscription probing deferred.** GraphQL subscriptions arrive via websocket and require a per-server lifecycle. detects subscription fields in the SDL but does not probe them. Full subscription coverage is planned for (chaos) where session lifecycle is already in scope.

## Consequences

**Positive:**

- Every API check is `httpx.MockTransport`-testable: unit tests run in milliseconds without spinning up a fixture server.
- The 64 KB ceiling is enforced at _three_ independent layers (config, I/O, check generator), so removing the guard requires three deliberate edits — and the security test fires on each one.
- Adding a new check kind requires only a new file in `modules/api/checks/` and one line in the `_RUN_ORDER` tuple; no lifecycle plumbing changes.
- Latency dedup is explicit and discoverable in the skip reason.

**Negative:**

- The negative-case catalogue is fixed; a real defect that only triggers under a variant we don't generate (e.g., specific Unicode boundary cases) goes undetected. Future phases that need broader variant coverage must add new named variants, not raise the cap.
- Subscription absence is a known coverage gap. Calls to a subscription field with no arguments still get logged as "skipped" without being marked as a deferred capability — the reader has to know to look at the chaos-module plan to find them.
- Backward-compat resolution prefers the alphabetically last sibling run, which mostly works because run-ids encode timestamps, but operators who archive runs out-of-band can pick the wrong baseline. The explicit `--diff-since` flag is the workaround; docs will call this out.

## Alternatives considered

- **TS-runtime-driven HTTP probing.** Reusing the Playwright context's request fixture would let the API module ride the same evidence pipeline as the functional module. Rejected because (a) it forces every API check to spin up Node + a browser context for what is fundamentally a Python HTTP client task, and (b) it introduces a second inter-runtime contract for negligible benefit.
- **openapi-core for end-to-end validation.** Drops the manual validation glue but pulls in a heavier dependency (and openapi-core 3.x has a churning API surface). Rejected for release; we may revisit for if the manual glue grows unwieldy.
- **Configurable "aggressive" mode behind proof-of-authorization.** Mirrors the security module's `authorized_destructive` posture for stored XSS / SQLi. Rejected: even with proof-of-authorization, un-targeted fuzzing of an API is bandwidth-expensive and rarely produces actionable findings. If a future user needs deep fuzzing, the right tool is a dedicated fuzzer (e.g., RESTler) wired in as a separate plugin under's plugin architecture, not a flag on the safe-by-default API module.
- **Live latency sampling in this module.** Rejected because already owns the budget and the goal is one finding per slow endpoint, not duplicates.

## References

- the documentation (API testing capabilities)
- our engineering rules(module contract), §30 (API testing rules), §6 (no fuzzing against unauthorized targets)
- ADR-0017 ( perf module) — perf budget contract
- ADR-0018 ( security module) — httpx client / SafetyPolicy pattern reused here
- — the per-task spec
