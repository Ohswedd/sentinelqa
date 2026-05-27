# SentinelQA error codes

Every typed error SentinelQA emits carries:

- A short symbolic `code` (e.g. `E-CFG-002`).
- A CLI `exit_code` from the deterministic grid in `PRD.md` §13.2 / `CLAUDE.md` §13.
- A human-readable `message`.
- A `suggested_fix` line.
- A redacted `context` dictionary.

The single source of truth is `engine/errors/codes.py:ERROR_REGISTRY`; this page is generated from it. When you add a code, add it there and re-render this page.

## Exit-code grid

| Exit code | Meaning               | Common cause                                                              |
| --------: | --------------------- | ------------------------------------------------------------------------- |
|         0 | Success               | The run completed and met all policy gates.                               |
|         1 | Quality gate failed   | Findings cleared the run but the configured policy blocked release.       |
|         2 | Configuration error   | `sentinel.config.yaml` missing, malformed, or carrying inline secrets.    |
|         3 | Runtime error         | Uncategorized non-fatal failure inside the engine.                        |
|         4 | Unsafe target blocked | Host not in `target.allowed_hosts`, or destructive mode without proof.    |
|         5 | Dependency missing    | Required Python or Node.js dependency unavailable; plugin failed to load. |
|         6 | Test execution failed | The Playwright runner or a module raised a non-recoverable failure.       |
|         7 | Internal error        | An assertion fired or an unexpected exception escaped.                    |

## Code catalog

### Configuration (exit 2)

- **E-CFG-001** — `Configuration file is missing or unreadable: {path}`
  - _Fix:_ Create `sentinel.config.yaml` at the project root or pass `--config <path>`.
- **E-CFG-002** — `Configuration failed schema validation: {detail}`
  - _Fix:_ Run `sentinel doctor` for a precise diff against the expected schema (PRD §17.1).
- **E-CFG-003** — `Inline secret detected at config key {field!r}; secrets must come from environment variables.`
  - _Fix:_ Replace the literal value with the corresponding `*_env` key (e.g. `password_env: TEST_USER_PASSWORD`).

### Safety boundary (exit 4)

- **E-SAFE-001** — `Host {host!r} is not in target.allowed_hosts and is not local.`
  - _Fix:_ Add the host to `target.allowed_hosts` ONLY if you own or are authorized to test it. SentinelQA never permits unauthorized scans (PRD §2, CLAUDE.md §6).
- **E-SAFE-002** — `Destructive mode requested for {host!r} without a valid proof-of-authorization document.`
  - _Fix:_ Provide `target.proof_of_authorization` pointing at a signed doc that covers this host, actor, and scope, and is not expired.
- **E-SAFE-003** — `Forbidden CLI flag {flag!r} requested; stealth/evasion/bypass features are not part of SentinelQA.`
  - _Fix:_ Remove the flag. See PRD §2.1 and CLAUDE.md §6 for the full forbidden list.

### Dependencies / plugins (exit 5)

- **E-DEP-001** — `Required dependency is missing: {dependency}`
  - _Fix:_ Run `make install` (or `uv sync --frozen --all-packages` and `pnpm install --frozen-lockfile`) and retry.
- **E-PLG-001** — `Plugin {plugin!r} could not be loaded: {detail}`
  - _Fix:_ Verify the plugin is installed, declares the expected entry point, and matches the host SentinelQA version.

### Runtime (exit 3) / test execution (exit 6) / internal (exit 7)

- **E-RUN-001** — `Test execution failed: {detail}` (exit 6)
  - _Fix:_ Inspect the Playwright trace and stdout under `.sentinel/runs/<run-id>/` for the failing step.
- **E-QGATE-001** — `Quality gate failed: {detail}` (exit 1)
  - _Fix:_ Either fix the underlying findings or adjust `policy` in `sentinel.config.yaml` if the gate is genuinely too strict.
- **E-INT-001** — `Internal SentinelQA error: {detail}` (exit 7)
  - _Fix:_ Re-run with `--verbose` and file a bug report including the captured stack trace; secrets are redacted by default.
- **E-PLG-002** — `Plugin {plugin!r} crashed at runtime: {detail}` (exit 7)
  - _Fix:_ Disable the plugin via `modules.<name>: false` while you diagnose; SentinelQA core continues without it.

## Machine-readable surface

The same registry powers `error.to_agent_message()` for SDK and MCP consumers:

```json
{
  "type": "error",
  "code": "E-SAFE-001",
  "exit_code": 4,
  "message": "Host 'evil.example.com' is not in target.allowed_hosts and is not local.",
  "suggested_fix": "Add the host to `target.allowed_hosts` …",
  "context": { "host": "evil.example.com" }
}
```

All fields are redacted before serialization (CLAUDE.md §33), so passing a `SentinelError` through `to_agent_message()` is safe in any logging or telemetry path.
