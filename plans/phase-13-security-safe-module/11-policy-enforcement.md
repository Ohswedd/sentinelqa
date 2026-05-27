# Task 13.11 — Policy enforcement re-check

## Deliverables

- Every public method in the module begins with `SafetyPolicy.enforce(target, mode)`.
- An automated test (`tests/security/test_module_calls_policy.py`) scans the module source AST and asserts every top-level method starts with a `SafetyPolicy.enforce` call (or delegates to one that does).
- Forbidden-flags audit: `--stealth`, `--evade`, `--bypass-*`, `--no-rate-limit`, `--ignore-robots` must NOT exist on any security subcommand. Test enforces.

## Acceptance criteria

- AST scan green.
- Forbidden-flag test green.

## PRD / CLAUDE.md references

- PRD §2.
- CLAUDE.md §6, §26.

## Definition of Done

- [ ] AST + forbidden-flag tests committed.
- [ ] `STATUS.md` updated.
