# Task 04.03 — `sentinel-ts` runner binary

## Objective

Implement the `sentinel-ts run` command that Python orchestrates. It reads a run-config JSON, executes Playwright with the right settings, and streams JSONL events to stdout while writing artifacts to the run dir.

## Deliverables

- `packages/ts-runtime/src/cli.ts` extended with subcommands:
  - `sentinel-ts run --input <path> --run-dir <path> [--shard N/M] [--workers W] [--browser chromium|firefox|webkit]`
  - `sentinel-ts list-tests --pattern <glob>`
  - `sentinel-ts validate-helpers` (sanity-checks that the helpers package is wired correctly).
- The run command:
  1. Reads `input` JSON describing: run id, target base URL, auth strategy hints, modules, test files, environment.
  2. Invokes `playwright test` programmatically (`@playwright/test/runtime` or `child_process.spawn('npx', ['playwright', 'test', ...])`) with the right config.
  3. Watches Playwright's stdout/reporter; translates events into the SentinelQA JSONL protocol.
  4. Writes artifacts (traces/screenshots/videos) into `<run-dir>/traces/`, `<run-dir>/screenshots/`, `<run-dir>/videos/`.
  5. Exits 0 if all tests passed, 1 if any failed, 2 if Playwright itself errored.
- Honors `--ci` (no progress spinners, JSONL only).

## Steps

1. Pick the invocation strategy. Prefer programmatic API for tight event capture; fall back to subprocess + custom Playwright reporter if simpler.
2. Implement a Playwright reporter plugin under `packages/ts-runtime/src/reporter.ts` that emits SentinelQA JSONL events.
3. Wire `sentinel-ts run` to invoke Playwright with the reporter.
4. Handle SIGINT cleanly (close browsers, flush artifacts).
5. Test against a tiny fixture project under `packages/ts-runtime/fixtures/sample-app/`.

## Acceptance criteria

- `sentinel-ts run` on the fixture project emits a JSONL event for every step and every test.
- Failures include trace, screenshot, and video paths.
- Exit code is deterministic.

## Tests required

- `tests/integration/runner.test.ts` — runs the fixture project end-to-end.

## PRD / CLAUDE.md references

- PRD §9.4 Runner, §11.3 Language strategy.
- CLAUDE.md §8 Runtime ownership.

## Definition of Done

- [ ] `sentinel-ts run` works on the fixture project.
- [ ] Event stream documented in ADR-0009.
- [ ] `STATUS.md` updated.
