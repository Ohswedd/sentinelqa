# Task 17.05 — Diff-aware test selection

## Deliverables

- `engine/ci/diff_aware.py` translating a git diff range to a set of impacted routes, components, and API endpoints.
- Heuristics:
  - Changed file path → if it matches a route file (`pages/...`, `app/...`, etc.), the corresponding routes are impacted.
  - Imported components → routes that import them are impacted (best-effort static analysis via Tree-sitter or `ts-morph` for TS / `ast` for Python).
  - Changed OpenAPI schema → affected endpoints' API tests are impacted.
- Output: list of test files + tags to run.
- Always also runs the mandatory smoke set (P0).

## Acceptance criteria

- A small one-file change runs a small subset.
- A change touching many files falls back to `full` mode.

## Tests required

- `tests/integration/ci/test_diff_aware.py`.

## PRD / CLAUDE.md references

- PRD §10.2, §12.3 PR diff audit.
- CLAUDE.md §17, §39.

## Definition of Done

- [ ] Diff-aware selection implemented and tested.
- [ ] `STATUS.md` updated.
