# Task 17.03 — PR comment poster

## Deliverables

- `integrations/github/post_pr_comment.py` — small helper invoked by the Action:
  - Reads `report.md`.
  - Finds an existing comment with the SentinelQA anchor (`<!-- sentinelqa:pr-comment -->`); if found, edits; otherwise creates.
  - Uses `GITHUB_TOKEN`. Never logs the token.
- Tolerant of rate limits; retries with backoff.
- A GitLab equivalent under `integrations/gitlab/post_mr_note.py`.

## Acceptance criteria

- First run posts; second run edits the same comment.

## Tests required

- `tests/integration/ci/test_pr_comment_poster.py` (mocks GitHub API).

## PRD / CLAUDE.md references

- PRD §21.2.
- CLAUDE.md §33.

## Definition of Done

- [ ] Posters work and are tested with mocks.
- [ ] `STATUS.md` updated.
