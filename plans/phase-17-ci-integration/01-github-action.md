# Task 17.01 — GitHub Action

## Deliverables

- `integrations/github/action.yml` — composite action with inputs:
  - `url` (required).
  - `config` (default `sentinel.config.yaml`).
  - `mode` (`fast`/`standard`/`full`/`nightly`/`release`).
  - `fail-under` (numeric override of `policy.min_quality_score`).
  - `diff` (e.g. `origin/main...HEAD`).
- Outputs: `quality-score`, `release-decision`, `report-html-url`.
- Steps (composite):
  1. Setup Python (cached), Node (cached).
  2. Install SentinelQA + `npx playwright install --with-deps`.
  3. Run `sentinel ci --mode <mode> --url <url> --diff <diff> --fail-under <n>`.
  4. Upload artifacts: `report.html`, `findings.json`, `sarif.json`, traces.
  5. Upload `sarif.json` to GitHub code scanning via `github/codeql-action/upload-sarif`.
- Reusable workflow `integrations/github/workflows/sentinel-pr.yml` that invokes the action.
- Marketplace-ready `action.yml` metadata (branding, description, icon).

## Acceptance criteria

- Action runs end-to-end on the example Next.js app (Phase 26) via a smoke workflow.
- Artifacts uploaded; SARIF visible in code scanning.

## Tests required

- `tests/integration/ci/test_github_action_smoke.yml` (workflow that runs the action against fixture).

## PRD / CLAUDE.md references

- PRD §21.1.
- CLAUDE.md §39.

## Definition of Done

- [ ] Action authored and smoke-tested.
- [ ] SARIF upload verified.
- [ ] `STATUS.md` updated.
