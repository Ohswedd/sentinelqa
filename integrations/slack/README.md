# Slack poster

/ — posts the Block Kit summary to an
incoming Slack webhook.

## Configuration

| Env var             | Required | Purpose                             |
| ------------------- | -------- | ----------------------------------- |
| `SLACK_WEBHOOK_URL` | yes      | Incoming webhook URL (read on call) |

our engineering rules §33 / §41: the webhook URL is a secret — it is never logged
in full. Log lines are rewritten via `integrations._http.redact_url`,
which strips both the query string and the userinfo segment.

## CLI

```
python -m integrations.slack.poster \ --payload.sentinel/runs/<run-id>/slack.json \ --webhook-env SLACK_WEBHOOK_URL \ --dedup-cache.sentinel/runs/<run-id>/slack-dedup.json
```

Exit codes: 0 success or dedup hit; 1 on transport / config failure.

## Programmatic use

The Phase-15 reporter generates the payload (see
`engine.reporter.slack.render_slack_payload`). The poster takes the
serialized dict and pushes it:: from integrations.slack import post_payload post_payload( payload=block_kit_dict, webhook_url=os.environ["SLACK_WEBHOOK_URL"], dedup_path=Path(".sentinel/runs/<id>/slack-dedup.json"), )

The `sentinel report --notify slack` CLI flag calls this
helper after re-rendering the report.

## Dedup window

The dedup cache key is `sha256(payload-json + webhook-host)`. Within
the window (default 300 s) repeating the same payload is a no-op so a
retried CI run does not double-post.
