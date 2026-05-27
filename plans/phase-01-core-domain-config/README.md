# Phase 01 — Core Domain & Configuration

## Objective

Build the typed core domain model (PRD §18), the strict `sentinel.config.yaml` loader/validator (PRD §17), the safety policy & target allowlist (PRD §2 / CLAUDE §6), the redaction utilities (CLAUDE §33), and the custom-exception hierarchy (CLAUDE §32). No I/O against a target yet — pure domain.

After this phase, the codebase has a fully-typed core: every later module imports its models from `engine.domain` and its config from `engine.config`.

## PRD / CLAUDE.md references

- PRD §2 Safety boundary, §17 Configuration, §18 Data model, §19 Quality scoring (entities only), §23 Threat model.
- CLAUDE.md §6 Safety boundary, §7 Architecture, §12 Config rules, §19 Code quality, §20 Python rules, §32 Error handling, §33 Logging & secrets, §43 Implementation Order (items 2–3).

## Sub-phases & tasks

1. `01-domain-models.md` — Pydantic models for Project, Target, DiscoveryGraph, Route, Element, Form, ApiEndpoint, Flow, TestCase, TestRun, ModuleResult, Finding, Evidence, QualityScore, PolicyDecision, RepairSuggestion.
2. `02-config-schema.md` — `sentinel.config.yaml` schema, strict validation, env interpolation, unknown-key rejection.
3. `03-safety-policy.md` — Target allowlist, host validator, destructive-mode gating, proof-of-authorization hook.
4. `04-exceptions.md` — Typed exception hierarchy mapped to CLI exit codes (PRD §13.2 / CLAUDE §13).
5. `05-redaction.md` — Real implementation of `redact()` covering passwords, tokens, cookies, auth headers, session IDs, API keys, private keys, PII.
6. `06-logging.md` — Structured logging with redaction, verbosity flags, JSON-mode silence.
7. `07-schema-versioning.md` — `SCHEMA_VERSION` constants, migration policy, deprecation notes.
8. `08-tests.md` — Comprehensive unit + property-based tests for all the above.

## Definition of Done

- Every domain entity in PRD §18.1 is implemented as a Pydantic model with full typing.
- `sentinel.config.yaml.example` is committed and round-trips through the loader.
- The safety policy refuses to run against non-allowlisted public targets by default and is unit-tested.
- Redaction handles every category in CLAUDE §33 with property-based tests.
- All custom exceptions map to deterministic exit codes (CLAUDE §13).
- ADR-0005 (Config schema) and ADR-0006 (Safety policy) committed.
- `PRD.md` updated wherever the implementation refined §17/§18.

## Phase Gate Review

- [ ] `mypy --strict` clean for `engine/domain`, `engine/config`, `engine/policy`.
- [ ] `pytest -q tests/unit/engine` ≥ 95% line coverage on the new modules.
- [ ] Loading the example config returns a fully-populated `Project` object.
- [ ] An unallowlisted host raises `UnsafeTargetError` and the CLI smoke test maps it to exit code 4.
- [ ] Redaction unit tests cover all CLAUDE §33 categories.
- [ ] ADR-0005, ADR-0006 committed.
- [ ] `STATUS.md` updated, gate row signed.
