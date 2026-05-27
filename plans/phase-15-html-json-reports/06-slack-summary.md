# Task 15.06 — Slack summary payload

## Deliverables

- `engine/reporter/slack.py` producing a Slack Block Kit JSON payload (no posting yet — Phase 25 posts).
- Sections: score, decision, top blockers, link to artifact, run id.
- Validates against Slack Block Kit schema (vendor the schema under `packages/shared-schema/external/`).

## Acceptance criteria

- Generated payload renders correctly in the Slack Block Kit Builder (manually verified once).

## Tests required

- `tests/golden/reports/test_slack_payload.py`.
- `tests/integration/reporter/test_slack_schema.py`.

## PRD / CLAUDE.md references

- PRD §9.7.
- CLAUDE.md §38.

## Definition of Done

- [ ] Payload generator + schema validation.
- [ ] `STATUS.md` updated.
