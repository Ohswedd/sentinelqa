# Task 15.02 — GitHub PR comment generator

## Deliverables

- `engine/reporter/pr_comment.py` exposing `render_pr_comment(run, findings, score, policy) -> str` returning GitHub-flavored Markdown.
- Content (PRD §21.2):
  - Score badge.
  - Release decision.
  - Critical findings list (top 5).
  - Changed flows tested (diff-aware mode).
  - Module summary.
  - Links to artifacts (Actions artifact URL).
  - Suggested next steps.
- Escapes Markdown in dynamic fields.
- The comment is **upserted** by the GitHub Action (Phase 17): same comment edited on subsequent runs instead of spawning new ones (anchor with `<!-- sentinelqa:pr-comment -->`).

## Acceptance criteria

- Renders within GitHub's 65k char limit.
- Comment is editable in place.

## Tests required

- `tests/golden/reports/test_pr_comment.py`.

## PRD / CLAUDE.md references

- PRD §21.2.
- CLAUDE.md §38.

## Definition of Done

- [ ] PR comment generator + golden.
- [ ] Upsert anchor in place.
- [ ] `STATUS.md` updated.
