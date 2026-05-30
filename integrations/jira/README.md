# Jira issue adapter

Phase 25 / task 25.06 — `create_issue(finding) -> issue_url`.

## Configuration

| Env var           | Required | Purpose                       |
| ----------------- | -------- | ----------------------------- |
| `JIRA_USER_EMAIL` | yes      | User email (HTTP Basic auth)  |
| `JIRA_API_TOKEN`  | yes      | API token (read at call time) |

The `base_url` (Atlassian cloud or self-hosted) must be passed
explicitly via `JiraCredentials(base_url=…)` and must use HTTPS.
The adapter never falls back to a default Jira URL.

## Behavior

- Off by default. Callers must supply `project_key`; this maps to
  `policy.integrations.jira.project_key` in config.
- The description is rendered through `engine.policy.redaction.redact`
  so credentials, tokens, and the like never reach Jira.
- Severity → priority mapping is fixed:
  critical → Highest, high → High, medium → Medium, low → Low,
  info → Lowest.

CI must not receive real `JIRA_*` credentials (see the credential
leak guard).
