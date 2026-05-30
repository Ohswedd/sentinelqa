# Task 36.07 — Publish runbook (owner-only)

## Deliverables

- `docs/release/publish-runbook.md`. The complete owner-action list:

  1. **Pre-flight** — confirm `docs/release/pre-1.0-review.md`
     `v1.0.0` block is signed (trademark rows complete, signature
     present).
  2. **Dry-runs** — run `python -m scripts.release.dry_run_pypi`,
     `dry_run_npm`, `dry_run_docker`. All exit 0.
  3. **Tag** — `git tag -s v1.0.0 -m "v1.0.0"`; `git push origin
     v1.0.0`. Signed tag (owner's GPG key).
  4. **Workflow approvals** — once the four publish workflows
     trigger on the tag, approve them in the GitHub Environments UI
     (`pypi-release` / `npm-release` / `docker-release` / `github-
     release`).
  5. **Verify** — run `SENTINELQA_TEST_POST_PUBLISH=1 uv run pytest
     tests/integration/release/test_post_publish_smoke.py -v`.
  6. **Announce** — drafts in `docs/release/announcement-draft.md`
     ready to post (Hacker News Show HN, Mastodon, Reddit r/devops,
     LinkedIn). Owner posts; agent does not.
  7. **Watch** — first 24 hours: monitor GitHub Issues, monitor
     `pypi.org/project/sentinelqa-cli/`, monitor Docker Hub pull
     stats. Document any post-publish hotfix process in
     `docs/release/post-publish-incident.md`.
- The runbook is the **only** doc that explicitly tells the agent
  not to run any publish command. The header carries the warning:
  > This page is for the human owner. SentinelQA's agent harness
  > will not run any `twine upload` / `pnpm publish` / `docker push`
  > / `git tag` step from this runbook — every command in this file
  > is something the owner runs themselves (CLAUDE.md §3 + §40).

## Tests required

- `tests/integration/docs/test_publish_runbook_complete.py` —
  runbook references every workflow file by path; every script
  exists; the warning header is present (lint guard).

## Definition of Done

- [ ] Runbook complete + reviewed.
- [ ] Lint guard active so a future edit can't strip the warning.
- [ ] `STATUS.md` updated.
