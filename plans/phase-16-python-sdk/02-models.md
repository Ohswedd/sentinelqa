# Task 16.02 — Public models

## Deliverables

- Re-export only the domain models intended as public from `sentinelqa`. Internal models (orchestrator state, redaction internals, runner-private structs) stay non-exported.
- Maintain `__all__` in `sentinelqa/__init__.py`.
- Every public model has a stable `schema_version` constant.
- Public models must be importable without triggering Playwright install or network calls.

## Acceptance criteria

- `python -c "import sentinelqa; print(sentinelqa.__all__)"` lists exactly the documented public surface.
- `import sentinelqa` runs under 200 ms.

## Tests required

- `tests/unit/sdk/test_public_surface.py`.
- `tests/unit/sdk/test_import_time.py`.

## PRD / CLAUDE.md references

- PRD §14.3.
- CLAUDE.md §14, §19.

## Definition of Done

- [ ] Surface frozen via tests.
- [ ] Fast import time enforced.
- [ ] `STATUS.md` updated.
