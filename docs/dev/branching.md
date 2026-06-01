# Branching policy

Status: `Stable`

Authority: project engineering rules. Implementation: this doc, `commitlint.config.cjs`, `.pre-commit-config.yaml`.

## The rule

> Never work directly on `main` unless explicitly instructed.

`main` is protected. All changes land via a pull request from a topic branch.

## Branch prefixes

Pick the prefix that best fits the change. One prefix per branch.

| Prefix      | When to use                                                    | Example                               |
| ----------- | -------------------------------------------------------------- | ------------------------------------- |
| `feature/`  | New product capability or new module phase                     | `feature/phase-05-discovery-crawler`  |
| `fix/`      | Bug fix in existing behavior                                   | `fix/cli-exit-code-on-missing-config` |
| `docs/`     | Documentation-only change (no code, no tests of code behavior) | `docs/agent-workflow-update`          |
| `refactor/` | Internal restructuring without behavior change                 | `refactor/extract-policy-loader`      |
| `security/` | Security boundary, hardening, secret hygiene                   | `security/redaction-coverage`         |
| `ci/`       | CI/CD workflow change                                          | `ci/cache-pnpm-store`                 |
| `chore/`    | Repo hygiene (configs, lockfiles, scaffolding)                 | `chore/bump-ruff-0.8`                 |
| `test/`     | Test-only additions/refactors                                  | `test/run-lifecycle-golden`           |
| `perf/`     | Performance work with measurable target                        | `perf/discovery-crawler-budget`       |
| `build/`    | Build system / packaging                                       | `build/sdist-metadata`                |

Phase work uses `feature/phase-<NN>-<short-slug>` (e.g. `feature/phase-00-foundation`). See §3.

## Authorship & ownership

> Git authorship must remain under the human owner or an explicitly configured human identity.
> No `Co-authored-by:` trailers for AI tools.
> No AI tools as owners or maintainers.

These are not soft conventions. CI fails any commit on a PR that lists an AI tool in a `Co-authored-by:` trailer (`.github/workflows/no-ai-coauthor.yml`, lands in Phase 00.08).

## What gets blocked locally

Pre-commit (`.pre-commit-config.yaml`) blocks:

- Secrets and private keys in any staged file (`gitleaks`, `detect-private-key`).
- Trailing whitespace, EOF without newline, mixed line endings, merge conflict markers, case conflicts, files > 2 MB.
- Python files that fail `ruff` or `ruff format --check`.
- Commit messages that don't match `commitlint`'s Conventional Commits rules (commit-msg stage).
- A `git push` whose branch fails `make ci` (pre-push stage runs format-check + lint + typecheck + tests).

The pre-push hook means you'll never push a branch that the CI matrix would reject — the gates run on your laptop first. If a hook genuinely cannot be satisfied (an emergency rollback, for instance), `--no-verify` is forbidden by our engineering rules

## What gets blocked on the remote

Branch protection on `main` (configured in the GitHub UI, documented in `docs/dev/ci-and-branch-protection.md` once Phase 00.06 lands) requires:

- `python` CI job green.
- `typescript` CI job green.
- `secret-scan` CI job green.
- `commitlint` CI job green.
- `no-ai-coauthor` CI job green.
- ≥ 1 approving review from a human CODEOWNER.

Direct pushes to `main` are rejected by branch protection.

## Pre-flight checklist before opening a PR

1. `make ci` is green locally.
2. Branch name uses one of the prefixes above.
3. Commits use Conventional Commits (`docs/dev/commits.md`).
4. `git log --grep="Co-authored-by"` shows no AI tool in any commit on the branch.
5. our product spec is updated if behavior, CLI/SDK contract, lifecycle, safety boundary, report schema, data model, or scoring changed.
6. New ADR added under `docs/adr/` if any our engineering rules
7. `STATUS.md` reflects the work done (active pointer advanced, task checkbox flipped).
8. `git status` is clean.
