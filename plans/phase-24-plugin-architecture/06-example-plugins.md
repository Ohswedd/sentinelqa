# Task 24.06 — Reference plugins

## Deliverables

- `examples/plugins/sentinelqa-scanner-example/` — a working `ScannerPlugin` with `pyproject.toml` + entry point + manifest.
- `examples/plugins/sentinelqa-reporter-example/` — a `ReporterPlugin` emitting a new format (e.g. CSV).
- Each example includes a README explaining how to install/develop/test.

## Acceptance criteria

- Installing each example into a fresh venv makes it discoverable by `sentinel plugins list`.

## Tests required

- `tests/integration/plugins/test_example_scanner.py`.
- `tests/integration/plugins/test_example_reporter.py`.

## PRD / CLAUDE.md references

- PRD §22.
- CLAUDE.md §22.

## Definition of Done

- [ ] Examples committed and tested.
- [ ] `STATUS.md` updated.
