# integrations/

Adapters for external systems. the documentation, §21, §25.

- `github/` — GitHub Action, PR comment poster, status checks (, §21.1).
- `gitlab/` — GitLab CI integration (, §21.1).
- `browserstack/` — remote cross-browser execution (, §25.x).
- `saucelabs/` — same.
- `slack/` — release-confidence webhooks.
- `jira/` — issue creation from findings (post-release).
- `linear/` — issue creation from findings (post-release).

Each integration is an adapter behind a port (our engineering rules, §35). The engine MUST NOT import these directly — it depends only on the ports.
