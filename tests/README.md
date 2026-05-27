# tests/

Cross-cutting test suites. PRD §11.2, CLAUDE §16.

- `unit/` — fast, isolated, pure-domain unit tests.
- `integration/` — multi-component tests, including Python ↔ TypeScript JSONL bridge.
- `e2e/` — end-to-end runs of SentinelQA against the example apps under `examples/`.

Per-package tests live next to the code they cover (e.g. `engine/policy/tests/`, `packages/ts-runtime/src/__tests__/`). This folder is for tests that span packages.
