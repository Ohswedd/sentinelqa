# Task 01.04 — Exception hierarchy & exit codes

## Objective

Implement a typed, narrow exception hierarchy that maps cleanly to the deterministic CLI exit codes (PRD §13.2 / CLAUDE §13). Per CLAUDE §32, expected errors must be typed, actionable, and carry a code, message, technical context, and suggested fix.

## Prerequisites

- Tasks 01.01–01.03 complete.

## Deliverables

- `engine/errors.py` defining:
  - `class SentinelError(Exception)` base. Attributes: `code: str` (e.g. `"E-CFG-001"`), `message: str`, `technical_context: dict[str, Any]`, `suggested_fix: str`, `redacted: bool`. Includes `to_agent_message()` returning a structured dict for SDK/MCP consumers.
  - `class ConfigError(SentinelError)` and subclasses: `ConfigFileNotFoundError`, `ConfigSchemaError`, `ConfigSecretInlineError`. Maps to exit code 2.
  - `class UnsafeTargetError(SentinelError)` + subclasses for `UnknownHost`, `DestructiveWithoutProof`, `ForbiddenFlag`. Exit code 4.
  - `class DependencyMissingError(SentinelError)`. Exit code 5.
  - `class TestExecutionError(SentinelError)`. Exit code 6.
  - `class QualityGateFailedError(SentinelError)`. Exit code 1.
  - `class InternalError(SentinelError)`. Exit code 7.
  - `class PluginError(SentinelError)`. Exit code 5 or 7 depending on cause.
- `engine/errors/codes.py` — single source of truth: tuple of `(code, exit_code, default_message_template, suggested_fix_template)` for every defined error. Used by `to_agent_message()` and by docs generation.
- `docs/user/error-codes.md` auto-generatable from `codes.py` (the Phase 27 docs site renders it).
- `engine/errors/render.py` — pretty-print errors with optional `--verbose` stack trace; JSON mode emits only the structured dict (CLAUDE §32 says verbose stack traces are for debug, not default UX).

## Steps

1. Implement the base `SentinelError` with `__init__(message, *, code=None, technical_context=None, suggested_fix=None)` that reads defaults from `codes.py` when `code` is given.
2. Implement each subclass with its code defaulted.
3. Implement `to_agent_message()` to produce a dict suitable for SDK return and MCP responses: `{type: "error", code, message, suggested_fix, context}` — redacted before return.
4. Implement `render.py` with two modes: `human` (color, indented) and `json` (single-line dict, no ANSI).
5. Update the CLI exit-code mapping function in `engine/policy/exit_codes.py` to read from `codes.py`.
6. Add a one-page error-code matrix `docs/user/error-codes.md`.

## Acceptance criteria

- Raising `ConfigSchemaError("..")` and catching at CLI boundary produces exit code 2.
- `error.to_agent_message()` contains no raw secret values (apply redaction first).
- JSON-mode rendering is single-line, valid JSON, no ANSI escapes.

## Tests required

- `tests/unit/errors/test_hierarchy.py` — every subclass maps to its expected exit code.
- `tests/unit/errors/test_agent_message.py` — round-trips; verifies redaction.
- `tests/unit/errors/test_render.py` — JSON mode is parseable; human mode includes the suggested fix.

## PRD / CLAUDE.md references

- PRD §13.2 Exit codes.
- CLAUDE.md §13 CLI rules, §32 Error handling.

## Definition of Done

- [ ] Exception hierarchy complete and unit-tested.
- [ ] Codes documented in `docs/user/error-codes.md`.
- [ ] CLI exit-code map function ready for Phase 02 to consume.
- [ ] `STATUS.md` updated.
