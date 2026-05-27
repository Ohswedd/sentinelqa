# Task 23.02 — Network chaos scenarios

## Deliverables

- TS helper `chaosNetwork(page, scenario)` supporting:
  - `slow_3g` — throttle to 400 Kbps / 400ms RTT.
  - `offline` — block all network.
  - `api_500` — match a URL pattern, return 500.
  - `api_timeout` — match pattern, never respond (then abort after 30s).
- Each scenario re-runs the target flow; findings categorize as `chaos-uncaught-error` when UI breaks (e.g. JS error, white screen).

## Acceptance criteria

- Fixture flow under `api_500` produces a finding if no error state shown (overlaps Phase 19.10).

## Tests required

- `tests/integration/modules/chaos/test_network.py`.

## Definition of Done

- [ ] Scenarios implemented + tested.
- [ ] `STATUS.md` updated.
