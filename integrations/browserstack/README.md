# BrowserStack adapter

Phase 25 / task 25.01 — adapter shaped like the SDK `RunnerPlugin`
Protocol (`sentinelqa.plugins`).

The adapter does **not** wire itself into `sentinel audit`. SentinelQA
remains location-agnostic; the engine never imports this module
directly . Operators opt in either via a custom runner
or by packaging the adapter as a plugin (Phase 24).

## Configuration

| Env var                   | Required | Purpose                                 |
| ------------------------- | -------- | --------------------------------------- |
| `BROWSERSTACK_USERNAME`   | yes      | Account username                        |
| `BROWSERSTACK_ACCESS_KEY` | yes      | Automate access key (read at call time) |

Credentials are read from the environment at construction
(`BrowserStackCredentials.from_env`). our engineering rules §33: they are never
logged, never written to disk, and never echoed in error messages.

## Behavior

- `map_capabilities(browser=, headless=, ...)` translates SentinelQA's Playwright-style invocation into BrowserStack Automate's capability payload (deterministic — same input → same JSON).
- `BrowserStackRunner.run(invocation, context)` creates a session and best-effort uploads any `trace_paths` to the Automate dashboard.
- HTTP 429 quota errors surface as `status="quota_exceeded"` in the outcome dict, not as exceptions — callers degrade to the local runner.

## Manual verification

This phase ships only mocked tests (no real provider call in CI).
A maintainer can verify end-to-end manually with:: export BROWSERSTACK_USERNAME=... export BROWSERSTACK_ACCESS_KEY=... python - <<'PY' from integrations.browserstack import BrowserStackRunner, BrowserStackCredentials runner = BrowserStackRunner(credentials=BrowserStackCredentials.from_env()) outcome = runner.run({"browser": "chromium", "headless": True, "run_id": "demo"}, context=None) print(outcome) PY

Real-provider smoke runs are NOT automated and MUST NOT receive
credentials in CI (see `tests/integration/integrations/test_credential_leak_guard.py`).
