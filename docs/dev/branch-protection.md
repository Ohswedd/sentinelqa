# Branch protection — source of truth

Status: `Stable`

Authority: `CLAUDE.md` §4 (Git workflow), §17 (Quality gates),
§39 (CI rules); `plans/phase-35-public-release/06-branch-protection.md`.

This file is the **machine-checkable** spec for the
`Ohswedd/sentinelqa` branch protection rules on `main`. It supersedes
the prose section in [`ci-and-branch-protection.md`](./ci-and-branch-protection.md)
for the public-release moment.

The owner applies these rules to the public repo via the GitHub UI or
`gh api` after task 35.08 flips visibility. The
`make verify-branch-protection` target reads the live GitHub config
and diffs it against this file — drift in either direction fails the
verification.

## TL;DR

`main` is protected. Every change goes through a PR with a human
review and a full green CI run. Force-pushes and deletions are
forbidden. Releases (`v*` tags) are admin-only.

## Required CI checks on `main`

The PR cannot merge until **every** check below has reported success
on the merge-base commit. Names must match the `name:` field in the
respective workflow exactly — GitHub matches by string.

| Check name               | Workflow file                          | What it gates                                                                   |
| ------------------------ | -------------------------------------- | ------------------------------------------------------------------------------- |
| `python (3.11)`          | `.github/workflows/ci.yml`             | Ruff format-check + lint, mypy strict, ADR check, pytest on Python 3.11.        |
| `python (3.12)`          | `.github/workflows/ci.yml`             | Same as above, on Python 3.12.                                                  |
| `typescript (node 20)`   | `.github/workflows/ci.yml`             | Prettier, ESLint, tsc --noEmit, Vitest on Node 20.                              |
| `typescript (node 22)`   | `.github/workflows/ci.yml`             | Same, on Node 22.                                                               |
| `docs (Astro Starlight)` | `.github/workflows/ci.yml`             | `make docs-build` + freshness gate (`make docs-check-fresh`).                   |
| `commitlint`             | `.github/workflows/commitlint.yml`     | Every commit in the PR range validated against `commitlint.config.cjs`.         |
| `gitleaks`               | `.github/workflows/secret-scan.yml`    | Secret scan over the PR diff (same pin as `.pre-commit-config.yaml`).           |
| `lychee`                 | `.github/workflows/link-check.yml`     | Internal Markdown link integrity.                                               |
| `no-ai-coauthor`         | `.github/workflows/no-ai-coauthor.yml` | Rejects any commit containing an AI tool in `Co-authored-by:` (`CLAUDE.md` §3). |

The `Docs deploy` workflow (Phase 35.04) is NOT a required check —
forks cannot run it, and an unreachable check would block fork PRs
forever. The job still runs on every PR and posts the preview URL.

## PR-flow rules on `main`

1. **Pull request required.** No direct pushes, ever.
2. **Approving reviews: 1** from a CODEOWNER who is not the author.
3. **Require review from CODEOWNERS:** enabled.
4. **Dismiss stale approvals on new commits:** enabled.
5. **Require conversation resolution:** enabled. Open review threads
   block merge.
6. **Require status checks to pass:** enabled. The check list is the
   table above.
7. **Require branches to be up to date before merging:** enabled.
8. **Require linear history:** enabled. Squash-merge is the default
   merge button; merge commits are disallowed.
9. **Require signed commits:** recommended (owner toggles once their
   GPG/Sigstore identity is published).
10. **Lock branch / Allow force-push / Allow deletion:** all **off**.
11. **Bypass settings:** none. Admins follow the same rules
    (`CLAUDE.md` §4); no `--admin` merge.

## Tag protection (`v*`)

A separate ruleset protects release tags:

- **Pattern:** `v*`.
- **Restrict creation to admins:** enabled.
- **Disallow force-update / deletion:** enabled.

Tags ratify a release per `docs/release/pre-1.0-review.md`; only the
owner can mint them.

## Verification

```bash
make verify-branch-protection
```

That target shells out to `scripts/release/verify_branch_protection.py`,
which calls:

```
gh api repos/Ohswedd/sentinelqa/branches/main/protection
```

…parses the response, and diffs it against the rules above. The script:

- Exits **0** if the live config matches.
- Exits **6** if it doesn't (printing a diff and an
  `https://github.com/Ohswedd/sentinelqa/settings/branches` link to
  re-apply).
- Exits **5** if `gh` isn't installed or isn't authenticated, with a
  pointer to `gh auth status`.

Until the repo is public, branch protection cannot be configured
(GitHub gates branch protection on private repos behind GitHub Pro).
Running `make verify-branch-protection` on the private repo prints a
clear "not yet applicable" message and exits 0.

## What to change here vs in GitHub

- **Rule changed in GitHub UI but not here** → drift; the verify
  script fails. Fix this file first, then re-apply.
- **Rule added here but not in GitHub** → drift; the verify script
  fails. Apply the rule via the GitHub UI / `gh api`, then re-run
  verification.
- **CI check renamed in `ci.yml`** → update the table above in the
  same PR. The verify script matches by exact string.

## Related

- [`.github/CODEOWNERS`](../../.github/CODEOWNERS) — who can approve.
- [`docs/dev/ci-and-branch-protection.md`](./ci-and-branch-protection.md) —
  prose overview; this doc is the machine-checkable spec.
- [`docs/release/pre-1.0-review.md`](../release/pre-1.0-review.md) —
  the gate that any `v*` tag must pass.
- [`plans/phase-35-public-release/06-branch-protection.md`](../../plans/phase-35-public-release/06-branch-protection.md) —
  task spec.
