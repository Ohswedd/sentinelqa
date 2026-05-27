# Task 25.03 — Slack poster

## Deliverables

- `integrations/slack/poster.py` posting the Phase 15.06 Block Kit payload to a webhook (`SLACK_WEBHOOK_URL`).
- Retries with backoff; deduplicates within 5-minute window.
- `sentinel report --notify slack` triggers it.

## Tests required

- `tests/integration/integrations/test_slack_mock.py`.

## Definition of Done

- [ ] Poster + tests.
- [ ] `STATUS.md` updated.
