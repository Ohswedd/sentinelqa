# Ownership, authorship, and AI-tool policy

Status: `Stable`

Authority: project engineering rules.0), `NOTICE`.

This document is the authoritative ownership policy for the SentinelQA repository. Every contributor — human or LLM agent — must comply.

## The rules (quoted from our engineering rules)

> The repository must stay private until the owner explicitly decides otherwise.
>
> Do not:
>
> - Make the repo public
> - Add AI tools, editors, models, or vendors as owners/co-owners
> - Add AI tools as package maintainers
> - Add `Co-authored-by:` trailers for AI tools unless explicitly requested
> - Add legal authorship, copyright, or ownership references to AI tools
> - Configure the editor, agent, or model as a project owner
>
> Git authorship must remain under the human owner or an explicitly configured human identity.

These rules are absolute. They are not subject to "but the agent did the work" rebuttals. The agent does work; the owner takes responsibility.

## Why

SentinelQA's product premise is **trust through evidence**. A product whose own provenance is unclear cannot credibly answer "can this software be trusted enough to ship?" for anything else. Ownership lock is part of the answer.

## What this means in practice

### Repository

- Default visibility: **private**. The owner is the only person who may flip it.
- Default branch: `main`. Branch protection (see `docs/dev/ci-and-branch-protection.md`) requires a PR + CODEOWNER review.
- `CODEOWNERS` lists humans only — `@ohswedd` is the seed entry. If your GitHub handle differs from the git committer name, update `.github/CODEOWNERS` before opening your first PR.

### Authorship

- Every commit's author + committer must be a human identity. `git config user.name` and `user.email` must be set locally to a real human's name/email — never to an AI tool, a vendor, or a generic "automation" identity.
- `Co-authored-by:` trailers naming an AI tool are forbidden. The CI workflow `.github/workflows/no-ai-coauthor.yml` rejects any push or PR whose commit messages contain the pattern.
- If the human owner explicitly types `Co-authored-by:` for _another human_ (paired work), that's fine — the workflow only blocks AI-tool names.

### License

- Apache-2.0 (`LICENSE` at repo root). The license choice is recorded in `ADR-0008` (lands in Phase 28 once a public release is in scope — for now the LICENSE file is the ground truth).
- `NOTICE` accumulates third-party attributions as production dependencies are added in later phases (Apache-2.0 requirement).

### Package & artifact ownership

- Python package metadata (`packages/python-sdk/pyproject.toml`, `apps/cli/pyproject.toml`): `authors = [{ name = "ohswedd" }]` only. No AI-tool maintainer entries.
- npm package metadata: no `maintainers` listing an AI tool.
- Future package-registry uploads (PyPI, npm) must be performed by the human owner under their personal credentials, not by a CI bot that masquerades as the owner.

## How CI enforces it

- **`.github/workflows/no-ai-coauthor.yml`** — scans commit messages in every PR and every push to `main` for `Co-authored-by:` lines naming any of: `Claude`, `GPT`, `Copilot`, `Gemini`, `Codex`, `Anthropic`, `OpenAI`, `Bard`, `Aider`, `Cursor`, `Devin`, plus future tools added to the pattern list. The match is case-insensitive.
- **`.github/CODEOWNERS`** — Branch protection's "Require review from Code Owners" rule, combined with this file's human-only listing, means every change is reviewed by a real person.
- **`.github/workflows/commitlint.yml`** — does NOT validate trailers (Conventional Commits doesn't speak to trailers), so the no-ai-coauthor workflow is the dedicated guard.

## How to add yourself as a contributor

1. Open a PR adding your real-name handle to `.github/CODEOWNERS` under whatever scope you own.
2. The current sole owner reviews and merges.
3. Your `git config user.name` / `user.email` must match a human identity for your commits to land cleanly.

## How to remove an unintended AI co-author trailer from history

If a commit accidentally lands with an AI co-author trailer:

1. Use `git rebase -i <commit>~1` and `reword` (or `git commit --amend` if it's the tip) to remove the trailer.
2. Force-push the _feature_ branch (force-pushing to `main` is forbidden — see our engineering rules).
3. The no-AI-coauthor workflow will go green on the next CI run.

## Trademark

The "SentinelQA" name has not been trademark-cleared. See `docs/dev/trademarks-and-naming.md` for the open work; Phase 28 owns the verification before any public release.
