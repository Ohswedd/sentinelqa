# Phase 15 — HTML & JSON Reports (full)

## Objective

Take the Phase 03 schema-locked report writers and produce the final, content-rich HTML report and the PR comment generator. Adds trend rendering when prior runs exist and a small static-site bundler so reports work offline.

## PRD / CLAUDE.md references

- PRD §9.7 Reporter, §20 Evidence, §21.2 PR comment, §28 Differentiation.
- CLAUDE.md §11, §38 Report rules.

## Sub-phases & tasks

1. `01-html-template.md` — Full HTML template; offline-capable.
2. `02-pr-comment.md` — GitHub PR comment generator.
3. `03-trends.md` — Show last N runs' scores when history exists.
4. `04-audit-trail-view.md` — Surface the audit log (with secrets redacted) inside the report.
5. `05-reporter-cli.md` — `sentinel report` command (generates / re-renders / explains).
6. `06-slack-summary.md` — Optional Slack summary payload (used by Phase 25).
7. `07-tests.md` — sweep + accessibility check on the report itself.

## Definition of Done

- HTML renders offline (no CDN dependencies).
- PR comment template tested against a real GitHub Markdown render.
- Trends render when history is available.
- The HTML report itself passes our own accessibility module on a smoke run.

## Phase Gate Review

- [ ] HTML opens correctly with file:// URL.
- [ ] No external network requests required to view the report.
- [ ] PR comment golden matches.
- [ ] Trends visible when history present.
- [ ] HTML passes axe-core smoke.
- [ ] `STATUS.md` updated.
