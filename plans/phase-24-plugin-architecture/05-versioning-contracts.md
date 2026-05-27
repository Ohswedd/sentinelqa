# Task 24.05 — Versioning contracts

## Deliverables

- Each Protocol declares a `PROTOCOL_VERSION` constant.
- Plugins declare `requires_protocol: ">=1.0,<2.0"`.
- Loader rejects plugins outside the declared range.
- Bumping `PROTOCOL_VERSION` requires an ADR.

## Acceptance criteria

- Plugin with incompatible requirement is rejected with a clear message.

## Tests required

- `tests/unit/plugins/test_versioning.py`.

## PRD / CLAUDE.md references

- PRD §22, §40.
- CLAUDE.md §22, §40.

## Definition of Done

- [ ] Versioning enforced + tested.
- [ ] `STATUS.md` updated.
