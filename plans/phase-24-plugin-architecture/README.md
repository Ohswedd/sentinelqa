# Phase 24 — Plugin Architecture

## Objective

Open SentinelQA to plugins (PRD §22, CLAUDE §22 plugin requirements): typed protocols for scanner, runner, reporter, policy, auth, data-fixture, and cloud-execution plugins. Discovered via Python entry points and TS package exports. Sandboxed where possible; capability + permission declarations enforced.

## PRD / CLAUDE.md references

- PRD §22 Plugin architecture.
- CLAUDE.md §22 (note: plugin rules also referenced in CLAUDE §35, §37).

## Sub-phases & tasks

1. `01-plugin-protocols.md` — Typed Protocols for each plugin kind.
2. `02-discovery-and-loading.md` — Entry points + load-time validation.
3. `03-capability-and-permission-declarations.md` — Manifest schema.
4. `04-sandboxing.md` — Process isolation for risky plugins (subprocess).
5. `05-versioning-contracts.md` — Plugin <-> core semver compatibility check.
6. `06-example-plugins.md` — Two reference plugins (custom scanner + custom reporter).
7. `07-cli-and-docs.md` — `sentinel plugins list` / `info <name>`; docs.
8. `08-tests.md` — sweep.

## Definition of Done

- Third party can ship a plugin via `pip install` + entry point, and it loads.
- Forbidden capabilities (CLAUDE §6 / Phase 01.03 forbidden list) are rejected at load.
- ADR-0021 (Plugin architecture) committed.

## Phase Gate Review

- [ ] Reference plugins work.
- [ ] Forbidden-capability rejection verified.
- [ ] Versioning compatibility tested.
- [ ] `STATUS.md` updated.
