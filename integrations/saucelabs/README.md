# Sauce Labs adapter

/ — adapter shaped like the SDK `RunnerPlugin`
Protocol. Same posture as the BrowserStack adapter :
the engine never imports this directly; operators opt in.

## Configuration

| Env var            | Required | Purpose                        |
| ------------------ | -------- | ------------------------------ |
| `SAUCE_USERNAME`   | yes      | Account username               |
| `SAUCE_ACCESS_KEY` | yes      | Access key (read at call time) |

`region` defaults to `us-west-1`; pass `region="eu-central-1"` or
`apac-southeast-1` for the other Sauce data centres.

## Behavior

- `map_capabilities(...)` translates SentinelQA's invocation into a W3C-shaped Sauce Labs capability payload with the `sauce:options` sidecar (deterministic).
- `SauceLabsRunner.run(invocation, context)` creates a job and best-effort uploads any `trace_paths` as job assets.
- HTTP 429 quota errors surface as `status="quota_exceeded"` — never exceptions — so callers can fall back to the local runner.

## Manual verification

CI runs only mocked tests. End-to-end smoke must be done locally:: export SAUCE_USERNAME=... export SAUCE_ACCESS_KEY=... python - <<'PY' from integrations.saucelabs import SauceLabsRunner from integrations.saucelabs.runner import SauceLabsCredentials runner = SauceLabsRunner(credentials=SauceLabsCredentials.from_env) outcome = runner.run({"browser": "chromium", "headless": True, "run_id": "demo"}, context=None) print(outcome) PY

CI must not receive real credentials (see the credential-leak guard).
