# Task 01.06 — Structured logging

## Objective

Provide a single logging facility used by every module. Logs must be structured (JSON Lines in CI/JSON mode, pretty in human mode), redacted by default, and respect `--quiet` / `--verbose` / `--ci` / `--json` from PRD §13.

## Prerequisites

- Task 01.05 complete.

## Deliverables

- `engine/logging/__init__.py` exposing:
  - `get_logger(name: str) -> SentinelLogger`.
  - `configure_logging(*, mode: Literal["human","json","quiet"], level: str, run_id: str | None)` — called once at CLI entry (Phase 02).
- Two formatters: `JSONFormatter` (one JSON object per line, fields: `ts`, `level`, `logger`, `msg`, `run_id`, `module`, `extra`) and `HumanFormatter` (color-coded, time, level, message).
- All log records pass through a `RedactionFilter` (uses `redact()` from task 01.05) before formatting.
- In `json` mode, **only** JSON lines reach stdout; warnings, info, debug go to stderr unless `--verbose`.
- `quiet` mode silences everything except errors.
- A `LogContext` helper attaches the active `run_id`, `module`, and `task_id` to every record via `contextvars`.
- `engine/logging/audit.py` distinct from operational logs — audit entries (safety decisions, policy gate outcomes) always go to `.sentinel/runs/<run-id>/audit.log` AND to stderr if `--verbose`.

## Steps

1. Build the `JSONFormatter` and `HumanFormatter`.
2. Build `RedactionFilter` calling `redact()` on `msg` and `extra`.
3. Wire `configure_logging` to set the right handlers/streams per mode.
4. Add `LogContext` with `__enter__`/`__exit__` and a decorator form.
5. Write unit tests that capture log output and assert structure + redaction.

## Acceptance criteria

- A log call `logger.info("hello", extra={"token": "sk-abc"})` becomes `... "extra": {"token": "[REDACTED:..."} ...`.
- In `json` mode, stdout is parseable JSONL; stderr carries human-friendly progress (only if verbose).
- In `quiet` mode, no INFO or DEBUG reaches any stream.

## Tests required

- `tests/unit/logging/test_formatters.py` — JSON parseable, fields present.
- `tests/unit/logging/test_redaction_filter.py` — secrets scrubbed.
- `tests/unit/logging/test_modes.py` — human/json/quiet modes behave correctly.

## PRD / CLAUDE.md references

- PRD §13 CLI rules.
- CLAUDE.md §13 CLI rules, §33 Logging & secrets.

## Definition of Done

- [ ] Logger configured by mode/level.
- [ ] Redaction always applied.
- [ ] Audit log separate stream.
- [ ] Tests pass.
- [ ] `STATUS.md` updated.
