# Task 24.03 — Capability & permission declarations

## Deliverables

- Plugin manifest schema (`packages/shared-schema/plugin-manifest.schema.json`):
  - `name`, `version`, `kind`, `capabilities[]`, `permissions[]` (e.g. `network.outbound`, `fs.read`, `fs.write:.sentinel/runs`, `subprocess.spawn`).
- Runtime enforcement: plugin only gets a `PluginContext` that exposes the permitted APIs.
- Permission requests beyond the declared set raise `PluginPermissionError`.

## Acceptance criteria

- Plugin without `fs.write` permission cannot write outside `.sentinel/runs`.

## Tests required

- `tests/integration/plugins/test_permissions.py`.

## PRD / CLAUDE.md references

- PRD §22.3.
- CLAUDE.md §22.

## Definition of Done

- [ ] Manifest schema + enforcement.
- [ ] `STATUS.md` updated.
