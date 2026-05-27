# Task 08.03 — Sharding & workers

## Objective

Add deterministic sharding and worker control so large suites scale across CI nodes.

## Deliverables

- Config keys: `runner.workers` (int or `auto` based on CPU count), `runner.shards` (`N/M` for splitting).
- CLI flags: `--workers`, `--shard` (mirrors Playwright's flag).
- Even sharding by test count; stable across runs (hash test path % shards).
- Aggregator that merges per-shard `ModuleResult` into a final one.

## Steps

1. Plumb the options through `LocalRunner` and `DockerRunner`.
2. Implement deterministic shard splitting.
3. Implement result merging (combines per-test results, sums durations, dedups evidence).

## Acceptance criteria

- 2-shard run of the fixture suite produces the same final result as a single-shard run (modulo ordering).
- Worker count respected.

## Tests required

- `tests/integration/runner/test_sharding.py`.

## PRD / CLAUDE.md references

- PRD §9.4, §21.
- CLAUDE.md §8, §39.

## Definition of Done

- [ ] Shard + worker controls work.
- [ ] `STATUS.md` updated.
