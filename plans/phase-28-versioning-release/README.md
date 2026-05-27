# Phase 28 — Versioning & Release Prep

## Objective

Prepare SentinelQA for its first tagged release (pre-1.0). Lock semver, changelog, package metadata, distribution scripts. Per CLAUDE §40, do not publish packages without explicit approval.

## PRD / CLAUDE.md references

- PRD §40 Versioning.
- CLAUDE.md §40 Versioning & release.

## Sub-phases & tasks

1. `01-semver-policy.md` — Pre-1.0 rules, breaking changes documented.
2. `02-changelog.md` — `CHANGELOG.md` with Keep-a-Changelog format.
3. `03-package-metadata.md` — `pyproject.toml`, `package.json` final metadata.
4. `04-distribution-scripts.md` — Build sdist/wheel, npm tarball, Docker image; verify contents.
5. `05-trademark-check.md` — Resolve `docs/dev/trademarks-and-naming.md` placeholder before any public release.
6. `06-pre-1.0-review.md` — Final go/no-go review.

## Definition of Done

- All packages buildable and inspectable.
- No release published yet (require human owner go-ahead).
- Pre-1.0 review checklist signed.

## Phase Gate Review

- [ ] `python -m build` produces clean sdist + wheel.
- [ ] `pnpm pack` produces tarballs.
- [ ] Docker image (runner) builds.
- [ ] Changelog includes everything since Phase 00.
- [ ] Trademark check completed.
- [ ] `STATUS.md` updated.
