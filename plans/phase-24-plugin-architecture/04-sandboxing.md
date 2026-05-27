# Task 24.04 — Sandboxing

## Deliverables

- For plugins requesting `subprocess.spawn` or `network.outbound`, run the plugin in a subprocess via `multiprocessing` or `subprocess` with a constrained env.
- Communication: a small JSON-over-stdio protocol so the sandboxed plugin returns its `ModuleResult` to the orchestrator.
- Optional OS-level sandboxing on Linux via `firejail` (best-effort; not required).

## Acceptance criteria

- Sandboxed plugin can't read environment variables it didn't request.
- Stdin/stdout protocol roundtrips a `ModuleResult`.

## Tests required

- `tests/integration/plugins/test_sandbox.py`.

## PRD / CLAUDE.md references

- PRD §22.3.
- CLAUDE.md §22.

## Definition of Done

- [ ] Sandbox implemented + tested.
- [ ] `STATUS.md` updated.
