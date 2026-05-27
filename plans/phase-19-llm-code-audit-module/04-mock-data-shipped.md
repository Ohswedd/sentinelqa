# Task 19.04 — Mock data shipped

## Deliverables

- Heuristic scan over loaded JS bundles + DOM:
  - Strings indicating mocks: `mockData`, `__MOCK__`, `lorem ipsum`, faker-like identifiers, hardcoded user lists with placeholder names ("John Doe", "Jane Doe", "test@test.com").
  - Same API response body across all calls (already detected in Phase 05.03; this module elevates it).
  - Hardcoded JSON imports of mock files (`data/mock.json`).
- Findings: `LLM-MOCK-DATA-SHIPPED`, severity high-medium depending on whether it's user-facing.

## Acceptance criteria

- Fixture page rendering hardcoded user list triggers finding.

## Tests required

- `tests/integration/modules/llm_audit/test_mock_data.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
