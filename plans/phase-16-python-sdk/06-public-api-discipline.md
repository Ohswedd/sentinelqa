# Task 16.06 — Public API discipline

## Deliverables

- `packages/python-sdk/sentinelqa/_internal/` for non-public helpers (single underscore prefix is a hard rule).
- A `__deprecation_policy.md` file in the SDK describing how breaking changes are announced (minimum one minor version of deprecation warnings before removal).
- A `make sdk-api-snapshot` task that writes the current public surface to `packages/python-sdk/api-snapshot.json`. CI compares; a diff requires an ADR.
- `ADR-0021` (Public SDK surface) committed. (Task originally specified ADR-0015; that ADR ID was consumed by Phase 10's module-contract decision. SDK ADR lands as ADR-0021.)

## Acceptance criteria

- Removing a public symbol fails CI unless an ADR + snapshot update accompany it.
- Internal symbols can be refactored freely.

## Tests required

- `tests/unit/sdk/test_api_snapshot.py`.

## PRD / CLAUDE.md references

- PRD §14, §40.
- CLAUDE.md §14, §40 Versioning.

## Definition of Done

- [ ] Snapshot in place; CI gate active.
- [ ] ADR-0021 committed.
- [ ] `STATUS.md` updated.
