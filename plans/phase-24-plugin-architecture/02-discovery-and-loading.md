# Task 24.02 — Plugin discovery & loading

## Deliverables

- Discovery via `importlib.metadata.entry_points(group="sentinelqa.plugins")`.
- Each plugin registers under its kind: `sentinelqa.scanners`, `sentinelqa.runners`, etc.
- Load-time validation:
  - Plugin class implements the declared Protocol.
  - Manifest matches schema.
  - Capabilities not in the forbidden list (Phase 01.03).
  - Version compatibility (semver range vs core).
- Failures: log and skip the plugin; do not crash the run.

## Acceptance criteria

- A test plugin shipped via local `pip install -e` loads automatically.
- A plugin declaring a forbidden capability is rejected with a clear error.

## Tests required

- `tests/integration/plugins/test_discovery.py`.

## PRD / CLAUDE.md references

- PRD §22.
- CLAUDE.md §6, §22.

## Definition of Done

- [ ] Discovery + validation + tests.
- [ ] `STATUS.md` updated.
