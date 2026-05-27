# Task 28.02 — Changelog

## Deliverables

- `CHANGELOG.md` in Keep-a-Changelog format.
- A `.github/changelog-template.md` for release notes.
- An automated PR step using `git-cliff` (or `conventional-changelog`) to suggest entries from Conventional Commits.

## Acceptance criteria

- Running `git-cliff -o CHANGELOG.draft.md` reproduces a sensible changelog.

## Tests required

- `tests/integration/release/test_changelog_drafting.py`.

## Definition of Done

- [ ] Changelog + tooling.
- [ ] `STATUS.md` updated.
