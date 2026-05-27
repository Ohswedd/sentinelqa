# Task 02.01 — Typer app skeleton

## Objective

Create the Typer CLI app in `apps/cli/` exposing every command from PRD §13.1, with global options matching CLAUDE §13.

## Prerequisites

- Phase 01 complete.

## Deliverables

- `apps/cli/sentinel/__init__.py` and `apps/cli/sentinel/__main__.py`.
- `apps/cli/sentinel/app.py` — top-level Typer app declaring:
  - Global options: `--config PATH` (default `sentinel.config.yaml`), `--json`, `--verbose`, `--quiet`, `--ci`, `--no-color`.
  - Commands (all registered, most as stubs raising `NotImplementedError` mapped to exit code 7 until their phase): `init`, `doctor`, `discover`, `plan`, `generate`, `test`, `audit`, `functional`, `api`, `a11y`, `perf`, `visual`, `security`, `chaos`, `llm-audit`, `fix`, `report`, `ci`, `mcp`.
  - A `--version` option printing the version from `pyproject.toml`.
- `apps/cli/sentinel/main.py` — `def main() -> int` entry point that:
  1. Calls `configure_logging()` based on global options.
  2. Invokes the Typer app inside a `try/except SentinelError` and maps to exit codes via `engine/policy/exit_codes.py`.
  3. Returns the integer exit code.
- Console script wired in `apps/cli/pyproject.toml`: `[project.scripts] sentinel = "sentinel.main:main"`.

## Steps

1. Build the Typer app and global options.
2. Register every command. Stubs print a one-line message `<command> not yet implemented (lands in phase XX)` then `raise NotImplementedError` mapped to exit code 7.
3. Implement `main()` with exception → exit-code mapping.
4. Add help text per command quoting the PRD §13 description.
5. Wire the console script and verify `sentinel --help`, `sentinel --version`, `sentinel doctor --help` all work.

## Acceptance criteria

- `pip install -e apps/cli && sentinel --help` lists every PRD §13.1 command.
- `sentinel --version` prints the version.
- Each stub command's exit code is 7 until implemented.
- Global options (`--json`, `--quiet`, etc.) propagate to logging configuration.

## Tests required

- `tests/integration/cli/test_app_help.py` — every PRD command appears in `--help`.
- `tests/integration/cli/test_global_options.py` — `--json` suppresses non-JSON output.
- `tests/integration/cli/test_version.py`.

## PRD / CLAUDE.md references

- PRD §13 CLI, §26 Skeleton.
- CLAUDE.md §13 CLI rules.

## Definition of Done

- [ ] All PRD §13.1 commands registered.
- [ ] Global options wired to logger.
- [ ] Console script installable.
- [ ] CLI tests pass.
- [ ] `STATUS.md` updated.
