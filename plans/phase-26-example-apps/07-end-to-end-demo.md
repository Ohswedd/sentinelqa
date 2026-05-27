# Task 26.07 — Full end-to-end demo

## Deliverables

- `examples/end-to-end-demo/` ties Next.js (frontend) + FastAPI (backend) together with `docker compose`.
- A `make demo` target that:
  1. Boots compose.
  2. Runs `sentinel audit --url http://localhost:3000`.
  3. Opens the generated HTML report.
- README walking through the demo with screenshots (no actual screenshots committed; use ASCII or links).

## Acceptance criteria

- `make demo` works in a fresh checkout.
- Audit completes in under 10 minutes on a developer laptop.

## Tests required

- `tests/integration/examples/test_end_to_end_demo.py` — compose up, audit, assert report exists, score ≥ threshold.

## Definition of Done

- [ ] Compose + audit demo working.
- [ ] `STATUS.md` updated; Phase 26 ready for gate.
