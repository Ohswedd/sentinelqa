# Task 32.07 — Secret-in-bundle scanner

## Deliverables

- `modules/security/checks/bundle_secrets.py`. Fetches every JS bundle
  Playwright loads (re-uses Phase 04's HAR capture; only URLs whose
  Content-Type is `application/javascript` / `text/javascript` are
  scanned) and scans each bundle for the patterns the Phase 29.02
  audit codified plus the Anthropic-Skills-recommended additions:
  - AWS keys (`AKIA[0-9A-Z]{16}`, `[A-Za-z0-9/+=]{40}` secret-shape
    when paired)
  - GCP keys (`AIza[…]{35}`)
  - Azure subscription keys (`[a-f0-9]{32}` in `subscription-key`
    context)
  - Stripe live keys (`sk_live_[…]{24,}`)
  - GitHub tokens (`gh[pousr]_[…]{36,}`)
  - Slack tokens (`xox[abprs]-…`)
  - JWT-shape (delegated to Phase 32.01)
  - Private-key headers (`-----BEGIN … PRIVATE KEY-----`)
- Findings carry `cwe_id: CWE-540` (Information Exposure Through
  Source Code), evidence (bundle URL + redacted match prefix), and a
  recommendation (move to server / `.env.local` / inject at build
  time).
- Bundles >= 5 MB are streamed and capped at 50 MB (configurable);
  beyond that the check emits a `truncated` flag in the finding (no
  silent skip).

## Tests required

- `tests/unit/modules/security/test_bundle_secret_patterns.py` — every
  pattern; redaction; truncation cap.
- `tests/integration/modules/security/test_bundle_scanner_e2e.py` —
  fixture serves a JS bundle with planted patterns; scanner finds
  them.

## Definition of Done

- [ ] Every pattern from Phase 29.02 is reachable.
- [ ] Streaming + cap honoured.
- [ ] `STATUS.md` updated.
