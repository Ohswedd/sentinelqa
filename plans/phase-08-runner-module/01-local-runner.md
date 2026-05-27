# Task 08.01 — Local Playwright runner

## Objective

Drive Playwright execution locally via the Phase 04 bridge, capturing the JSONL stream and producing a typed `ModuleResult`.

## Deliverables

- `engine/runner/local.py` exposing `LocalRunner.run(test_files: list[Path], *, config: RootConfig, run_dir: Path) -> ModuleResult`.
- Spawns `sentinel-ts run` as a subprocess with appropriate args; streams stdout JSONL into the parser.
- Captures stderr (redacted) into `<run-dir>/logs/runner.log`.
- Maps Playwright statuses to SentinelQA statuses (`passed`, `failed`, `flaky`, `skipped`, `timed_out`).
- Records every test's evidence paths.

## Steps

1. Implement subprocess management with `asyncio.create_subprocess_exec`.
2. Wire the JSONL parser from Phase 04 task 04.04.
3. Aggregate events into a `ModuleResult`.
4. Add timeouts; SIGINT propagation; ensure Playwright shuts down cleanly.

## Acceptance criteria

- Running the fixture spec via `LocalRunner.run([fixture_spec])` returns a populated `ModuleResult`.
- Process is killed gracefully on SIGINT.

## Tests required

- `tests/integration/runner/test_local_runner.py`.
- `tests/unit/runner/test_event_aggregation.py`.

## PRD / CLAUDE.md references

- PRD §9.4.
- CLAUDE.md §8, §9.

## Definition of Done

- [ ] Local runner implemented and tested.
- [ ] `STATUS.md` updated.
