# Task 35.07 — Security advisories + Dependabot

## Deliverables

- `SECURITY.md` (from task 35.02) carries the private disclosure flow:
  - Preferred: GitHub Private Vulnerability Reporting (enabled once
    the repo is public).
  - Alternative: `security@sentinelqa.dev` (placeholder; owner sets
    up the inbox).
  - 90-day disclosure deadline; coordinated disclosure encouraged.
- `.github/dependabot.yml` covers:
  - Python ecosystem on `uv.lock` (weekly, grouped by minor/patch).
  - npm ecosystem on `packages/ts-runtime/package.json` + root
    `package.json` (weekly).
  - GitHub Actions (weekly).
  - `docker` ecosystem on `apps/cli/sentinel/runner/docker/Dockerfile.runner`
    (weekly).
- `docs/dev/security-policy.md` explains:
  - Supported versions ('latest minor only' pre-1.0; switch at 1.0.0
    to 'latest two minors').
  - Severity ratings via CVSS v4.0.
  - Embargo + advisory publication timeline.

## Tests required

- `tests/integration/release/test_dependabot_config.py` — YAML
  validates against the Dependabot schema; covers all four
  ecosystems.

## Definition of Done

- [ ] `SECURITY.md` shipped.
- [ ] Dependabot covers all four ecosystems.
- [ ] `docs/dev/security-policy.md` written.
- [ ] `STATUS.md` updated.
