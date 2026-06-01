# Publish runbook

Status: `Stable`

This is the runbook a maintainer follows to cut a real SentinelQA
release. Every command is something a human runs locally; nothing in
this file delegates publishing to automation.

> ⚠️ **Maintainers only.** Tagging and publishing are gated on the four `<env>-release` GitHub Environments. Do not run `git tag`, `twine upload`, `pnpm publish`, or `docker push` without working through this runbook first.

## Workflow files

The four publish workflows triggered by a `v*` tag push:

- `.github/workflows/publish-pypi.yml` — six Python distributions to PyPI via Trusted Publisher OIDC.
- `.github/workflows/publish-npm.yml` — `@sentinelqa/ts-runtime` to npm with provenance.
- `.github/workflows/publish-docker.yml` — `sentinelqa/runner` to Docker Hub for `linux/amd64` + `linux/arm64`.
- `.github/workflows/github-release.yml` — GitHub Release with the wheels + sdists + TS tarball as assets.

---

## Pre-flight

These checks gate the tag. If any check fails, stop the publish and
fix the underlying problem before retrying.

### 1. Confirm `main` is releasable

- `make ci` is green on the merge commit you intend to tag.
- `make coverage` ≥ 95 %.
- `make audit-metadata` reports clean.
- `make audit-license-headers` reports clean.
- `make build-all` produces the expected 13 artifacts at the target version.
- `make inspect-all` reports no forbidden contents.
- `CHANGELOG.md` has a curated `## [<tag>] - YYYY-MM-DD` section above `[Unreleased]`.
- [`docs/dev/semver.md`](../dev/semver.md) tag-plan row for the tag reflects what actually ships.

### 2. Run every dry-run locally

Each registry has a paired dry-run that exercises the build + validate
path **without** publishing.

```bash
# PyPI: build every sdist + wheel, then `twine check --strict`.
uv run python -m scripts.release.dry_run_pypi --out-dir dist

# npm: build @sentinelqa/ts-runtime, pack, inspect the tarball,
# and run `npm publish --dry-run --access public`.
uv run python -m scripts.release.dry_run_npm --out-dir dist/npm

# Docker Hub: `docker buildx build --platform linux/amd64,linux/arm64 --no-push`.
uv run python -m scripts.release.dry_run_docker

# GitHub Release: confirm the CHANGELOG slice for the tag renders.
uv run python -m scripts.release.extract_release_notes v1.0.0 -o /tmp/release-notes.md
less /tmp/release-notes.md
```

Every dry-run must exit `0`. If any of them fails, stop — pushing the
tag will trigger the matching publish workflow, and the workflow will
fail the same way.

### 3. Confirm the GitHub Environments are wired

In `Settings → Environments` on `github.com/Ohswedd/sentinelqa` verify
each of the four publish environments exists and requires manual
approval:

- `pypi-release` — PyPI Trusted Publisher OIDC; no secret to store.
- `npm-release` — requires the `NPM_TOKEN` secret.
- `docker-release` — requires `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN`.
- `github-release` — no secret; runs as the repo's default token.

For each environment: `Required reviewers = maintainers`, `Deployment
branches and tags = matching tags v*`.

The PyPI Trusted Publisher entry must exist at
<https://pypi.org/manage/account/publishing/> for every publishable
Python package (`sentinelqa-cli`, `sentinelqa-engine`,
`sentinelqa-modules`, `sentinelqa-integrations`, `sentinelqa`,
`sentinelqa-mcp`). Fields: `Owner = Ohswedd`, `Repository name =
sentinelqa`, `Workflow filename = publish-pypi.yml`, `Environment =
pypi-release`.

---

## Tag

Once every pre-flight check is green, cut the tag from the
already-merged commit on `main`. The tag must be GPG-signed.

```bash
# From a clean main on the commit you've validated above:
git checkout main
git pull --ff-only origin main

# Confirm the commit SHA matches the one your pre-flight ran against.
git log -1 --format="%H %s"

# Cut the signed tag.
git tag -s v1.0.0 -m "v1.0.0"

# Push the tag (this triggers all four publish workflows).
git push origin v1.0.0
```

Pushing the tag is the moment of no-return: the four publish workflows
start immediately, gated only on the per-environment approvals you
wired in step 3.

---

## Approve each publish

Watch the `Actions` tab — four workflows queue against your
environments:

1. **`Publish (PyPI)`** → click "Review deployments" → "Approve and deploy". Watch the `verify` job install from PyPI and report `sentinel --version`.
2. **`Publish (npm)`** → same approval flow. Watch the `verify` job poll `npm view @sentinelqa/ts-runtime@<tag>` until it returns the right version.
3. **`Publish (Docker Hub)`** → same approval flow. Watch the `verify` job pull the image, assert the manifest carries `linux/amd64` + `linux/arm64`, and run `sentinel --version` inside the image.
4. **`Publish (GitHub Release)`** → same approval flow. Confirm the release notes render correctly and every artefact (wheels + sdists + TS tarball) appears under "Assets".

If any verify job fails, **do not** retry the workflow. Yank the
just-published version per the
[`docs/dev/semver.md`](../dev/semver.md) yanking procedure and cut a
new patch.

---

## Verify

Once all four workflows are green, run the post-publish smoke test
against the live registries to confirm everything works for an outside
consumer:

```bash
SENTINELQA_TEST_POST_PUBLISH=1 \
  uv run pytest tests/integration/release/test_post_publish_smoke.py -v
```

The smoke test pip-installs from PyPI, npm-installs from npm, pulls
from Docker Hub, and runs `sentinel --version` against each of them.
The tag is read from `apps/cli/pyproject.toml` so it stays accurate
across future bumps.

---

## Announce

Post the release notes to your communication channels of choice
(release thread, social, blog). Link to the GitHub Release page;
do not paste the full changelog inline.

---

## Watch (24 hours)

For the first 24 hours after a publish:

- Monitor <https://github.com/Ohswedd/sentinelqa/issues> for new bug reports.
- Monitor <https://pypi.org/project/sentinelqa-cli/> for download stats and any yank requests.
- Monitor <https://hub.docker.com/r/sentinelqa/runner> for pull stats and reported issues.

If a critical post-publish issue surfaces:

1. Cut a fix on a branch off `main`; PR + merge; cut a patch tag (`v1.0.1`).
2. Yank the broken version on PyPI + npm (don't delete it; yanking preserves history).
3. Document the yank under the new patch's `### Removed` block in `CHANGELOG.md`.

---

## What this runbook explicitly does not authorise

- **Skipping the dry-runs.** They are local and cheap; their job is to surface broken state before the publish runs in CI.
- **Tagging without a green `make ci`.** A failing tag is a yanked tag.
- **Force-pushing a tag.** If a tag goes out wrong, yank and cut the next patch.

---

# This is the only document that actually publishes SentinelQA to the public registries. Read it twice before running.
