# Phase 36 — Publish to the Ecosystem

## Objective

Tag `v1.0.0` and publish the seven artifacts to their respective public
registries: six Python packages to PyPI, one TypeScript package to npm,
one Docker image to Docker Hub, plus a GitHub Release that links it all.
This is the last phase of the build plan and the very last items are
**explicitly owner-gated** (CLAUDE.md §40 — "Do not publish packages
without explicit approval").

This phase ships everything the publish needs: the workflows, the
secrets layout, the dry-run scripts, the post-publish smoke tests. The
agent does **not** run any `twine upload` / `pnpm publish` / `docker
push` itself — those are owner commands.

## PRD / CLAUDE.md references

- PRD §32 (Recommended build order — publishing is last).
- CLAUDE.md §3 (Ownership), §40 (Versioning + release — explicit
  approval), §41 (Privacy + telemetry — no usage telemetry shipped).

## Sub-phases & tasks

1. `01-v1-tag-prep.md` — Bump every manifest to `1.0.0`; curate the
   `CHANGELOG.md` `[1.0.0]` section; finalise `docs/dev/semver.md`
   tag-plan row; refresh the SDK api-snapshot; rebuild + inspect all
   artifacts.
2. `02-pypi-publish.md` — `.github/workflows/publish-pypi.yml`
   triggered on `v*` tag push; uses `pypa/gh-action-pypi-publish`
   with Trusted Publisher (no long-lived API token); dry-run script
   `scripts/release/dry_run_pypi.py`.
3. `03-npm-publish.md` — `.github/workflows/publish-npm.yml` triggered
   on `v*` tag push; provenance via `--provenance` flag; dry-run
   script `scripts/release/dry_run_npm.py`.
4. `04-docker-publish.md` — `.github/workflows/publish-docker.yml`;
   builds + pushes `sentinelqa/runner:<version>` + `:latest` (and SHA
   pin) to Docker Hub with multi-arch via Buildx (amd64 + arm64).
5. `05-github-release.md` — `.github/workflows/github-release.yml`
   uses `softprops/action-gh-release`; attaches the wheels + sdists +
   TS tarball as assets; release notes from `CHANGELOG.md`.
6. `06-post-publish-smoke.md` — `tests/integration/release/test_post_publish_smoke.py`
   (gated): pip-installs from PyPI, npm-installs from npm,
   docker-pulls from Docker Hub; runs `sentinel --version` etc.
7. `07-publish-runbook.md` — `docs/release/publish-runbook.md` is the
   step-by-step owner action list. The very last line:
   `# This is the only time SentinelQA actually publishes to the
   public registries. Read it twice before running.`

## Definition of Done

- Every publish workflow ships, dry-run scripts work, post-publish
  smoke test is ready to run.
- `docs/release/publish-runbook.md` is unambiguous about what the
  owner clicks / runs.
- ADR-0048 (Publish pipeline) accepted.

## Phase Gate Review

- [ ] All four publish workflows committed.
- [ ] Trusted-publisher / provenance configured.
- [ ] Dry-run scripts exit clean on the current `main`.
- [ ] Smoke test ready.
- [ ] Publish-runbook reviewed.
- [ ] ADR-0048 accepted.
- [ ] No `twine upload` / `pnpm publish` / `docker push` performed by
      the agent — those are owner commands.
- [ ] `STATUS.md` updated.
