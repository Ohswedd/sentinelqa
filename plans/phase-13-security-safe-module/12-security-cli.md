# Task 13.12 — `sentinel security` command

## Deliverables

- Replace Phase 02 stub of `security`.
- Options: `--url`, `--config`, `--mode safe|authorized_destructive`, `--proof-of-authorization <path>`, `--checks <list>`, `--ci`, `--json`.
- Enforces refusal at runtime, not just at config load.

## Tests required

- `tests/integration/cli/test_security.py` — refusal scenarios + happy path.

## Definition of Done

- [ ] CLI command implemented and tested.
- [ ] `STATUS.md` updated.
