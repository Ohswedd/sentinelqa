# Task 25.04 — GitHub deeper integration

## Deliverables

- Status check poster: `integrations/github/status.py` posts a commit status with the quality score and decision (used by branch protection in Phase 17).
- Issue creator: when a `critical` finding lacks an existing tracking issue, optionally open one (`policy.github.auto_create_issue: false` by default).
- Issue body uses the finding's evidence + suggested fix; PII redacted.

## Tests required

- `tests/integration/integrations/test_github_status.py`.
- `tests/integration/integrations/test_github_issue_create.py`.

## Definition of Done

- [ ] Adapters + tests.
- [ ] Auto-issue creation off by default.
- [ ] `STATUS.md` updated.
