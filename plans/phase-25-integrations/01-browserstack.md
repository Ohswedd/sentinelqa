# Task 25.01 — BrowserStack adapter

## Deliverables

- `integrations/browserstack/runner.py` implementing the `RunnerPlugin` Protocol (Phase 24).
- Uses Playwright's BrowserStack support (`browserstack/playwright`); env vars `BROWSERSTACK_USERNAME`, `BROWSERSTACK_ACCESS_KEY`.
- Maps SentinelQA `RunMode` to BrowserStack capabilities.
- Uploads traces; falls back gracefully if quota exceeded.
- Documented at `integrations/browserstack/README.md`.

## Tests required

- `tests/integration/integrations/test_browserstack_mock.py`.

## Definition of Done

- [ ] Adapter present + mock-tested.
- [ ] `STATUS.md` updated.
