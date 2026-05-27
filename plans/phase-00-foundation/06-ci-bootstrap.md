# Task 00.06 — CI bootstrap

## Objective

Set up GitHub Actions so every PR runs the full quality-gate matrix from `CLAUDE.md` §17 against both Python and TypeScript packages.

## Prerequisites

- Tasks 00.01–00.05 complete.

## Deliverables

- `.github/workflows/ci.yml` running on `pull_request` and `push` to `main` with at least two jobs:
  - `python` matrix on `ubuntu-latest` (and `macos-latest` if cheap), Python 3.11 + 3.12 — runs `make install`, `make lint`, `make typecheck`, `make test`.
  - `typescript` on `ubuntu-latest`, Node 20 + 22 — runs `pnpm install --frozen-lockfile`, `pnpm -r run lint`, `pnpm -r run typecheck`, `pnpm -r run test`.
- `.github/workflows/secret-scan.yml` running `detect-secrets` (or `gitleaks`) on every PR.
- `.github/workflows/commitlint.yml` running commitlint against PR commits.
- `.github/CODEOWNERS` with the human owner; **no AI tools** listed.
- `.github/pull_request_template.md` linking to `CLAUDE.md` §18 Definition of Done and listing the required checkboxes.
- `.github/ISSUE_TEMPLATE/bug_report.md` and `feature_request.md`.
- Cached install steps for `uv`/`pnpm` to keep CI fast.
- Branch protection rule documentation in `docs/dev/ci-and-branch-protection.md` (the rule itself is configured in the GitHub UI, but the doc records the required checks).

## Steps

1. Write `ci.yml` with explicit named steps for each gate (one step per check so CI logs are easy to read).
2. Configure caches: `actions/setup-python` with `cache: pip` (or `uv` cache), `actions/setup-node` with `cache: pnpm`.
3. Always run `npx playwright install --with-deps chromium` in TS jobs — even if no tests use it yet, fail fast if the dep is broken.
4. Make the workflow upload artifacts on failure (`actions/upload-artifact` for `tests/**/junit.xml`, `playwright-report/**`).
5. Verify by opening a no-op PR; both jobs must go green.
6. Document the branch protection requirements: PRs require `python` + `typescript` + `secret-scan` + `commitlint` checks passing; no direct pushes to `main` (`CLAUDE.md` §4).

## Acceptance criteria

- A PR with a deliberate lint error is **blocked**.
- A PR with the test smoke files only is **green** end-to-end.
- Secret-scan job fails fast on a PR containing a fake token.

## Tests required

- The CI workflow itself; verified by a no-op PR pass.

## PRD / CLAUDE.md references

- PRD §21 CI/CD Requirements.
- CLAUDE.md §17 Quality Gates, §39 CI Rules.

## Definition of Done

- [ ] `ci.yml`, `secret-scan.yml`, `commitlint.yml` all merged and green.
- [ ] CODEOWNERS + PR template + issue templates in place.
- [ ] Branch protection documented.
- [ ] No AI tool referenced anywhere in `.github/`.
- [ ] `STATUS.md` updated.
