# integrations/

Adapters for external systems. the documentation, §21, §25.

- `github/` — GitHub Action, PR comment poster, status checks (Phase 17, §21.1).
- `gitlab/` — GitLab CI integration (Phase 17, §21.1).
- `browserstack/` — remote cross-browser execution (Phase 25, §25.x).
- `saucelabs/` — same (Phase 25).
- `slack/` — release-confidence webhooks (Phase 25).
- `jira/` — issue creation from findings (post-MVP).
- `linear/` — issue creation from findings (post-MVP).

Each integration is an adapter behind a port (our engineering rules, §35). The engine MUST NOT import these directly — it depends only on the ports.
