# Task 01.07 — Schema versioning policy

## Objective

Define and enforce the schema-versioning policy for every machine-readable artifact SentinelQA produces (CLAUDE §11, §15.4, §24). Set the precedent now so Phase 03 (reports) and Phase 16 (SDK) inherit a consistent rule.

## Prerequisites

- Tasks 01.01 and 01.04 complete.

## Deliverables

- `engine/domain/schema.py` listing every artifact and its current version:
  - `RUN_SCHEMA_VERSION = "1"`.
  - `FINDINGS_SCHEMA_VERSION = "1"`.
  - `SCORE_SCHEMA_VERSION = "1"`.
  - `CONFIG_SCHEMA_VERSION = "1"`.
  - `REPAIR_SUGGESTION_SCHEMA_VERSION = "1"`.
  - `AGENT_MESSAGE_SCHEMA_VERSION = "1"`.
- `docs/dev/schema-versioning.md` — written policy:
  - Schemas use a single integer (major). Breaking changes bump the integer.
  - Every machine-readable artifact MUST include `schema_version` at its root.
  - Forward compatibility: readers MUST accept additional unknown fields **only** if the schema doc explicitly permits it (default: no).
  - Deprecation lifecycle: announce in release notes one minor version before removing.
  - Migration: each artifact has a `migrations/<from>_to_<to>.py` if it ever needs one.
- `engine/domain/migrations/__init__.py` — registry stub; no migrations yet because everything starts at version 1.
- A repo-wide schema-validation CI step: any committed `*.schema.json` is checked with `check-jsonschema`; any committed `*.golden.json` is validated against its schema.

## Steps

1. Centralize the constants in `engine/domain/schema.py`.
2. Update every domain model that emits an artifact to include `schema_version: str = Field(default=<constant>)`.
3. Write the policy doc.
4. Wire the CI step.

## Acceptance criteria

- Every artifact-producing model carries the version constant.
- Removing a constant or changing it without an ADR fails CI.
- Policy doc is referenced from `CONTRIBUTING.md`.

## Tests required

- `tests/unit/domain/test_schema_versions.py` — every artifact serialization carries the version.

## PRD / CLAUDE.md references

- PRD §18, §20.
- CLAUDE.md §11 Artifact rules, §40 Versioning & release.

## Definition of Done

- [ ] Constants centralized.
- [ ] Policy doc committed.
- [ ] CI step enabled.
- [ ] `STATUS.md` updated.
