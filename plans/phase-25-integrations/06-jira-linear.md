# Task 25.06 — Jira & Linear issue adapters

## Deliverables

- `integrations/jira/issue.py` — `create_issue(finding) -> issue_url`.
- `integrations/linear/issue.py` — same.
- Config: `policy.integrations.jira.project_key`, `policy.integrations.linear.team_id`.
- Both off by default; require explicit enable + token.

## Tests required

- `tests/integration/integrations/test_jira_mock.py`.
- `tests/integration/integrations/test_linear_mock.py`.

## Definition of Done

- [ ] Adapters + tests.
- [ ] `STATUS.md` updated.
