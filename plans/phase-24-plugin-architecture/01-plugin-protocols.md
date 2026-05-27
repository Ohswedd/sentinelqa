# Task 24.01 — Plugin Protocols

## Deliverables

- `packages/python-sdk/sentinelqa/plugins.py` defining typed Protocols (PRD §22.2):
  - `ScannerPlugin`, `RunnerPlugin`, `ReporterPlugin`, `PolicyPlugin`, `AuthPlugin`, `DataFixturePlugin`, `CloudExecutionPlugin`, `DiscoveryPlugin`.
- Each Protocol declares:
  - `name: str`, `version: str`, `capabilities: frozenset[str]`, `permissions: frozenset[str]`.
  - One or more methods specific to its purpose (e.g. `ScannerPlugin.run(ctx) -> ModuleResult`).

## Acceptance criteria

- A class implementing `ScannerPlugin` registers via entry points and runs.

## Tests required

- `tests/unit/plugins/test_protocols.py`.

## PRD / CLAUDE.md references

- PRD §22.2.
- CLAUDE.md §22 (referenced via "plugin requirements").

## Definition of Done

- [ ] Protocols + tests.
- [ ] `STATUS.md` updated.
