# Task 13.01 — Security module skeleton

## Deliverables

- `modules/security/__init__.py` exposing `SecurityModule(SentinelModule)`.
- Every public method calls `SafetyPolicy.enforce()` before issuing network requests.
- Registered with orchestrator.

## Tests required

- `tests/unit/modules/test_security_skeleton.py`.

## PRD / CLAUDE.md references

- PRD §10.7, §26.
- CLAUDE.md §6, §9, §26.

## Definition of Done

- [ ] Skeleton + tests.
- [ ] `STATUS.md` updated.
