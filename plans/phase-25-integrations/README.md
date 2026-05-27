# Phase 25 — Integrations

## Objective

Wire the integrations listed in PRD §11.2 / §32: BrowserStack, Sauce Labs (remote browsers), Slack (notifications), GitHub (deeper integration: issues, status checks, code-scanning), and Jira/Linear stubs. Each integration ships behind a feature flag and uses dedicated env vars.

## PRD / CLAUDE.md references

- PRD §11.2, §32, §22 plugins.
- CLAUDE.md §35 Dependency rules, §41 Telemetry.

## Sub-phases & tasks

1. `01-browserstack.md` — Remote browser execution adapter.
2. `02-saucelabs.md` — Same, for Sauce Labs.
3. `03-slack.md` — Slack webhook poster reusing Phase 15.06 payload.
4. `04-github-deeper.md` — GitHub status checks, issue creator for blockers.
5. `05-gitlab-deeper.md` — GitLab MR notes + commit statuses.
6. `06-jira-linear.md` — Issue creation stubs.
7. `07-tests.md` — sweep (mocks; no real provider calls in CI).

## Definition of Done

- Each adapter behind config + env var; off by default.
- Mocked tests cover happy + failure paths.
- Real-provider smoke documented as manual verification.

## Phase Gate Review

- [ ] All adapters present + mocked-tested.
- [ ] No real provider call in CI.
- [ ] `STATUS.md` updated.
