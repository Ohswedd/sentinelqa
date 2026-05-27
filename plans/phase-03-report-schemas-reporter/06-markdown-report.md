# Task 03.06 — Markdown report

## Objective

Emit a concise Markdown report (`report.md`) optimized for PR comments and quick scanning. The full HTML report lands in Phase 15.

## Deliverables

- `engine/reporter/markdown_writer.py` exposing `write_markdown(dir, run, findings, score, policy) -> Path`.
- Structure:
  - Title with quality score and release decision badge.
  - One-paragraph summary (run id, target, duration, modules run).
  - Critical/blocked findings as a bullet list, each with its `id`, title, severity, and artifact link.
  - Per-module mini-table (status, finding counts).
  - Footer with links to the HTML report (relative path) and trace artifacts.
- Use a deterministic Markdown style (no random ordering, consistent table widths).
- All user-controlled content escaped (no Markdown injection from finding titles).

## Steps

1. Implement the writer.
2. Add a small Markdown escape helper.
3. Build goldens for: passing, blocked, unsafe_blocked, dry_run.

## Acceptance criteria

- Renders correctly in GitHub's PR comment preview.
- No HTML injection via finding fields.

## Tests required

- `tests/golden/reports/test_markdown.py`.

## PRD / CLAUDE.md references

- PRD §21.2 PR comment.
- CLAUDE.md §38 Report rules.

## Definition of Done

- [ ] Markdown writer + goldens committed.
- [ ] Escapes verified.
- [ ] `STATUS.md` updated.
