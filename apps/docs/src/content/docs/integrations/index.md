---
title: Integrations
description: Stdlib HTTP adapters for the cloud and SaaS services SentinelQA composes with.
status: Stable
---

Every integration ships as a small adapter under `integrations/`
behind a shared stdlib HTTP helper (`integrations/_http.py`). No
third-party HTTP client. No vendor SDK. Off by default; secrets are
read from env vars only and redacted in every log line.

Authority: the documentation, ADR-0030.

## Adapters

| Adapter      | Purpose                                                |
| ------------ | ------------------------------------------------------ |
| BrowserStack | Remote browser runner                                  |
| Sauce Labs   | Remote browser runner (multi-region)                   |
| Slack        | Post a Block Kit summary on completion                 |
| GitHub       | PR comment + commit status + (gated) auto-create issue |
| GitLab       | MR note + commit status                                |
| Jira         | `create_issue(finding) -> issue_url`                   |
| Linear       | GraphQL `IssueCreate` mutation                         |

## Slack quickstart

```bash
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
uv run sentinel report --latest --notify slack
```

The poster:

- Reads the webhook from env (never config).
- Posts the [ Block Kit payload](/cli/#sentinel-report).
- Deduplicates by `sha256(webhook URL + payload)` over a 5-minute window — re-running `sentinel report` won't spam the channel.
- Never breaks JSON-mode stdout.

## GitHub PR comments

Wire via the GitHub Action (see [CI/CD](/cicd/)). The poster upserts
on the anchor `<!-- sentinelqa:pr-comment -->`, so each PR has at
most one SentinelQA comment that is overwritten in place.

## Credential safety

`tests/integration/integrations/test_credential_leak_guard.py` fails
on every CI pass if any secret env var is non-empty during
the test run. Tokens never appear in test fixtures or commits.
