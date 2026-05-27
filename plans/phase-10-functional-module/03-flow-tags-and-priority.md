# Task 10.03 — Tag-driven selection

## Objective

Allow users to run a subset by tag (`--grep @p0`, `--grep @flow:login`) so CI modes (Phase 17) can target the right slice cheaply.

## Deliverables

- Generated specs always tag with: `@p0..p3`, `@flow:<name>`, `@module:functional`, `@risk:<level>`.
- The runner's `--grep` flag accepts tags and patterns.
- Predefined slices: `--mode smoke` (= `@p0`), `--mode standard` (= `@p0,@p1`), `--mode full` (no filter).

## Steps

1. Make tag emission consistent across templates.
2. Add slice mode option to the CLI.
3. Tests.

## Acceptance criteria

- `--mode smoke` runs only `@p0` specs.
- `--grep @flow:login` runs only login specs.

## Tests required

- `tests/integration/modules/functional/test_tags.py`.

## PRD / CLAUDE.md references

- PRD §13, §21.3 CI modes.
- CLAUDE.md §13.

## Definition of Done

- [ ] Tags consistent.
- [ ] Slice modes work.
- [ ] `STATUS.md` updated.
