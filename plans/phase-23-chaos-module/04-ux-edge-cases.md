# Task 23.04 — UX edge cases

## Deliverables

- Duplicate submit: click submit twice rapidly; expect server-side idempotency or UI disabling.
- Double-click race: rapid clicks on the same primary action; observe network duplication.
- Browser back-forward across multi-step forms.
- Refresh mid-flow (especially during a payment or form submit).
- Findings:
  - Duplicate orders / records observed in API → high.
  - Lost form state → medium.
  - White-screen on refresh → high.

## Acceptance criteria

- Fixture allowing duplicate submits → finding.

## Tests required

- `tests/integration/modules/chaos/test_ux_edge.py`.

## Definition of Done

- [ ] Scenarios + tests.
- [ ] `STATUS.md` updated.
