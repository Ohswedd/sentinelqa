# Task 23.05 — Data chaos scenarios

## Deliverables

- Empty dataset: mock the list-API to return `[]`; verify empty-state UI present.
- Large dataset: mock the list-API to return 1000 items; verify pagination or virtualization (no DOM explosion).
- Browser storage corruption: write garbage into `localStorage` for known keys; verify app does not crash (graceful fallback or fresh load).
- Findings: missing empty state (high), DOM explosion (medium), crash on corrupted storage (high).

## Acceptance criteria

- Fixture without empty state → finding.

## Tests required

- `tests/integration/modules/chaos/test_data.py`.

## Definition of Done

- [ ] Scenarios + tests.
- [ ] `STATUS.md` updated.
