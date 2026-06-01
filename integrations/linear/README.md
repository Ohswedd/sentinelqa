# Linear issue adapter

Phase 25 / task 25.06 — `create_issue(finding) -> issue_url`.

## Configuration

| Env var          | Required | Purpose                                  |
| ---------------- | -------- | ---------------------------------------- |
| `LINEAR_API_KEY` | yes      | API key (sent as `Authorization` header) |

## Behavior

- Off by default. Callers must supply `team_id`; this maps to `policy.integrations.linear.team_id` in config.
- Description text passes through `engine.policy.redaction.redact`.
- Severity → priority mapping: critical=1 (Urgent), high=2, medium=3, low=4, info=0.

Linear uses GraphQL at `https://api.linear.app/graphql`; the adapter
sends the `IssueCreate` mutation and returns the issue's `url`.

CI must not receive a real `LINEAR_API_KEY` (see the credential leak
guard).
