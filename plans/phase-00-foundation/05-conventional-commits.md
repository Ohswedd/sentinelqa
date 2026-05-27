# Task 00.05 — Conventional Commits & branch policy

## Objective

Enforce the commit-message and branching conventions in `CLAUDE.md` §4 so every change in the repo is structured, auditable, and machine-parseable for future changelog generation.

## Prerequisites

- Tasks 00.01–00.04 complete.

## Deliverables

- `commitlint.config.cjs` declaring `extends: ['@commitlint/config-conventional']` with the type whitelist limited to: `feat`, `fix`, `docs`, `test`, `refactor`, `security`, `ci`, `chore`, `perf`, `build`.
- `.husky/commit-msg` hook (or pre-commit hook entry) that runs commitlint on the staged message.
- `.husky/pre-push` hook that runs `make ci` (lint+typecheck+test) before any push.
- `docs/dev/branching.md` documenting:
  - Branch prefixes (`feature/`, `fix/`, `docs/`, `refactor/`, `security/`, `ci/`, `chore/`).
  - The rule that `main` is protected and direct commits are forbidden (`CLAUDE.md` §4).
  - The rule that AI tools are never added as Git authors or co-authors (`CLAUDE.md` §3).
- A short `docs/dev/commits.md` with at least 8 worked examples (feat / fix / security / docs / refactor / ci / chore / perf).

## Steps

1. Install commitlint + husky as dev deps in the root `package.json`.
2. Configure husky (`npx husky init`), then add the `commit-msg` and `pre-push` hooks.
3. Add a `commitlint.config.cjs` with the strict type whitelist.
4. Test the hook by attempting `git commit -m "bad message"` — must be rejected.
5. Test that `git commit -m "feat(repo): example"` is accepted.
6. Write `docs/dev/branching.md` and `docs/dev/commits.md`.
7. Update `CONTRIBUTING.md` (created in task 00.09) to reference these docs.

## Acceptance criteria

- Bad commit messages are rejected locally.
- The phase commits land with valid Conventional-Commit messages.
- No AI co-author trailer exists in any commit (`git log --all --grep="Co-authored-by.*Claude" --oneline` is empty).

## Tests required

- Hook-rejection demonstrated locally; capture the output in the PR description (do not commit poisoned messages).

## PRD / CLAUDE.md references

- CLAUDE.md §3 Privacy/ownership, §4 Git workflow.

## Definition of Done

- [ ] commitlint + husky installed and active.
- [ ] Bad message blocked, good message accepted.
- [ ] Branching + commit docs written.
- [ ] `STATUS.md` updated.
