# Task 16.04 — Async support

## Deliverables

- Every long-running operation has an async counterpart (`async_audit`, `async_discover`, `async_plan`, `async_generate_tests`, `async_run_plan`, `async_verify_fix`).
- Internally uses `asyncio` with subprocess management.
- Sync versions are thin wrappers around the async versions via `asyncio.run()`.

## Acceptance criteria

- Both sync and async APIs work and produce identical results for the same input.

## Tests required

- `tests/integration/sdk/test_async_audit.py`.

## PRD / CLAUDE.md references

- PRD §14.4.
- CLAUDE.md §14.

## Definition of Done

- [ ] Async API present; tests confirm parity.
- [ ] `STATUS.md` updated.
