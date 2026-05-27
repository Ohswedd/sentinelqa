# Task 01.01 — Domain models

## Objective

Implement every core entity from PRD §18.1 as a fully-typed Pydantic v2 model in `engine/domain/`.

## Prerequisites

- Phase 00 complete (tooling green).

## Deliverables

A new package `engine/domain/` exposing:

- `Project` — name, root path, framework, package manager, version, schema_version.
- `Target` — base_url, allowed_hosts (frozenset[str]), mode (`safe` / `authorized_destructive`), proof_of_authorization (optional ref).
- `Route` — path, method, http_methods, auth_required, parent_template (e.g. `/users/[id]`).
- `Element` — id, role, accessible_name, selector, location (route), tags.
- `Form` — id, action_url, method, fields[], submit_handler_present (bool), validation_present (bool).
- `ApiEndpoint` — method, path, request_schema, response_schema, auth_strategy, source (`discovered` / `openapi` / `graphql`).
- `Flow` — id, name, steps[], priority (P0..P3), risk (critical/high/medium/low), required_auth_role, required_data_state.
- `TestCase` — id, flow_id, file_path (relative to `tests/sentinel`), test_type (`functional`/`a11y`/etc.), confidence (0–1).
- `TestRun` — id, started_at, finished_at, target, config_snapshot, modules_run[], status (`passed`/`failed`/`incomplete`/`unsafe_blocked`).
- `ModuleResult` — name, status, findings[], metrics{}, duration_ms, errors[].
- `Finding` — id, run_id, module, category, severity (`critical`/`high`/`medium`/`low`/`info`), confidence, title, description, evidence[], location, recommendation, created_at, schema_version. (PRD §18.2 is the wire format.)
- `Evidence` — type (`screenshot`/`video`/`trace`/`har`/`console_log`/`network_log`/`dom_snapshot`/`stack_trace`/`api_sample`/`source_ref`), path, redacted (bool).
- `QualityScore` — total (0–100), components{name → score}, weights{}, severity_penalties_applied, schema_version.
- `PolicyDecision` — release_decision (one of PRD §19.3), blocked_by[], reasons[].
- `RepairSuggestion` — target_test, original, proposed, confidence, reason, evidence[], requires_human_review (bool). (Schema must match CLAUDE §23 contract.)
- `DiscoveryGraph` — routes[], elements[], forms[], api_endpoints[], auth_boundaries[].
- `RiskMap` — per-route risk score, justifications, derived from DiscoveryGraph.

Constraints:

- All models inherit from a `SentinelModel` base that sets `model_config = ConfigDict(frozen=True, extra="forbid")`.
- Every model has a `SCHEMA_VERSION` ClassVar (string, semver-major-only, e.g. `"1"`).
- IDs use a small prefix-based generator (`PRJ-`, `RUN-`, `MOD-`, `FND-`, etc.) implemented in `engine/domain/ids.py` and unit-tested for collision resistance.
- All datetimes are timezone-aware UTC (`datetime.now(timezone.utc)`).

## Steps

1. Scaffold `engine/domain/__init__.py` re-exporting public types.
2. Implement `SentinelModel` base + `ids.py` + `schema.py` (holding `SCHEMA_VERSION` constants).
3. Implement each model in its own file (`project.py`, `target.py`, …).
4. Add `__all__` to each module and to the package `__init__`.
5. Add JSON Schema generation: `engine/domain/jsonschema.py` exposes `dump_schemas(out_dir: Path)` that writes one `*.schema.json` per model. Wire it to a `make schemas` target.
6. Add round-trip tests: every model can be serialized to JSON and parsed back.

## Acceptance criteria

- `from engine.domain import Finding, TestRun, ...` works.
- `make schemas` produces stable JSON Schema files in `packages/shared-schema/`.
- `pydantic` rejects unknown fields (`extra="forbid"`) — proven with a test.
- All IDs validate against their regex.

## Tests required

- `tests/unit/domain/test_models.py` — instantiation + round-trip for every model.
- `tests/unit/domain/test_ids.py` — collision/format tests.
- `tests/unit/domain/test_schemas.py` — generated JSON Schemas validate sample payloads.
- Property-based tests (hypothesis) for IDs, severity bounds, confidence range.

## PRD / CLAUDE.md references

- PRD §18 Data Model.
- CLAUDE.md §19 Code quality, §20 Python rules, §37 No placeholder completion.

## Definition of Done

- [ ] Every entity in PRD §18.1 implemented.
- [ ] JSON Schemas generated and committed.
- [ ] Tests above pass, ≥95% coverage on `engine/domain/`.
- [ ] No `Any`, no untyped public function.
- [ ] `STATUS.md` updated.
