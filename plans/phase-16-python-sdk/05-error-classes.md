# Task 16.05 — Public error classes

## Deliverables

- Re-export the user-facing exception classes from Phase 01:
  - `SentinelError`, `ConfigError`, `UnsafeTargetError`, `DependencyMissingError`, `TestExecutionError`, `QualityGateFailedError`.
- Provide `sentinelqa.errors.from_dict(agent_message: dict) -> SentinelError` for reconstructing an error from an agent message.
- Document each in `docs/user/error-codes.md`.

## Acceptance criteria

- Reconstructed errors have the same `code` and `suggested_fix` as the originals.

## Tests required

- `tests/unit/sdk/test_error_roundtrip.py`.

## PRD / CLAUDE.md references

- PRD §14.4.
- CLAUDE.md §32.

## Definition of Done

- [ ] Errors exported + reconstructible.
- [ ] `STATUS.md` updated.
