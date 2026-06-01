# CI and branch protection

Status: `Stable`

. our product spec (CI/CD requirements).

This doc captures the required GitHub-side configuration. The workflow files themselves live under `.github/workflows/`; this doc tells the repo administrator what to wire up in the GitHub UI on top of them.

## Workflows in this repo

| Workflow        | File                                   | Trigger                          | What it gates                                                                                                                                                                                |
| --------------- | -------------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CI              | `.github/workflows/ci.yml`             | `pull_request`, `push` to `main` | Python (3.11 + 3.12) and TypeScript (Node 20 + 22) matrices: ruff format-check + lint, mypy strict, pytest; prettier-check, eslint, tsc --noEmit, vitest; Playwright Chromium install smoke. |
| Secret scan     | `.github/workflows/secret-scan.yml`    | `pull_request`, `push` to `main` | gitleaks against the full PR diff (same pin as `.pre-commit-config.yaml`).                                                                                                                   |
| Commitlint      | `.github/workflows/commitlint.yml`     | `pull_request`                   | Every commit in the PR range validated against `commitlint.config.cjs`.                                                                                                                      |
| No AI co-author | `.github/workflows/no-ai-coauthor.yml` | `pull_request`, `push` to `main` | Rejects any commit message containing `Co-authored-by:` followed by a known AI-tool string.                                                                                                  |

## Required branch-protection rules for `main`

Configure these in **GitHub → Settings → Branches → Branch protection rules** for the `main` branch:

1. **Require a pull request before merging.** - Required approving reviews: **1**. - Require review from Code Owners: **enabled**. - Dismiss stale approvals when new commits are pushed: **enabled**.
2. **Require status checks to pass before merging.** - Require branches to be up to date before merging: **enabled**. - Required checks (the names below must match the `name:` fields in each workflow): - `python (3.11)` - `python (3.12)` - `typescript (node 20)` - `typescript (node 22)` - `gitleaks` - `commitlint` - `no-ai-coauthor` (added in )
3. **Restrict who can push to matching branches.** Even with approvals, only repo admins may push directly — and even then only for emergencies. our engineering rules`main`.
4. **Require linear history.** No merge commits; PR merges land as squash or rebase.
5. **Require signed commits.** Optional but recommended (configure once lands the release-signing rules).
6. **Restrict force-pushes.** Disallow force-push to `main` for everyone. (Force-push to feature branches is fine; our engineering rules-push to `main`.)
7. **Lock the branch?** No — but the rules above effectively make `main` write-only via PR.

## Required repository settings

- **Default branch:** `main`.
- **Default merge button:** `Squash and merge` (keeps the linear history of feature branches readable).
- **Auto-delete merged branches:** enabled.
- **Visibility:** `private` until the human owner explicitly publishes.
- **Collaborators:** human only. No AI tools, no bot accounts that act as members. The `gitleaks` GitHub Action runs as `GITHUB_TOKEN`, which is fine — that token is scoped per workflow and is not a member.

## What this means for contributors

- You cannot push directly to `main`.
- Every PR must come from a topic branch (`feature/...`, `fix/...`, etc. — see `docs/dev/branching.md`).
- A PR cannot merge until the seven workflow checks above are green AND a human CODEOWNER has approved it.
- Pre-push hooks (`.pre-commit-config.yaml`, pre-push stage) run the same gates locally so you never push a branch that the CI would reject.

## Verification gap

The CI workflow files in this commit were written and statically validated (YAML parses; structure follows GitHub Actions schema) but have **not yet been executed against a real PR**, because the repository is local-only at the time of this Phase-00 commit. The gate review records this as a deferred verification: the first PR opened against `main` on the GitHub remote MUST exercise all four workflows; any divergence between the documented gates and the actual run must be fixed before begins.

## How to add a new required check

1. Add the workflow under `.github/workflows/`.
2. Name the `job.name:` exactly as you want it to appear in the required-checks list.
3. Update this doc to list the new check.
4. In the GitHub UI, add the new check name to the branch-protection required-checks list.
5. Open a test PR; verify the new check actually blocks a known failure case.
