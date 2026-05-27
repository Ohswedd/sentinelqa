# Task 29.01 — Safety audit

## Deliverables

- Audit every module that performs I/O against a target. For each, confirm:
  - `SafetyPolicy.enforce()` is called before any network call.
  - No `--stealth` / `--evade` / `--bypass-*` flags exist.
  - User-Agent header transparent.
  - `X-SentinelQA-Test-Run` header sent.
  - Rate limits applied.
  - Audit log entry per significant decision.
- Run a "red team" against the binary: attempt to scan `https://example.com` without allowlist and with destructive mode. Document refusal logs.
- Result: a one-page `docs/release/safety-audit-<date>.md` with verdicts per module.

## Acceptance criteria

- Audit signed off and committed.

## Definition of Done

- [ ] Audit doc committed.
- [ ] `STATUS.md` updated.
