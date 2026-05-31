# Publish runbook (owner-only)

> ⚠️ **This page is for the human owner. SentinelQA's agent harness will not run any `twine upload` / `pnpm publish` / `docker push` / `git tag` step from this runbook — every command in this file is something the owner runs themselves (`CLAUDE.md` §3 + §40).**

Status: `Stable`

Authority: `CLAUDE.md` §3 (Ownership), §40 (Versioning & release
rules), §41 (Privacy & telemetry). `docs/dev/semver.md` (tag plan).
`docs/release/pre-1.0-review.md` (sign-off contract). ADR-0048
(publish pipeline).

## Workflow files

The four publish workflows triggered by a `v*` tag push:

- `.github/workflows/publish-pypi.yml` — six Python distributions
  to PyPI via Trusted Publisher OIDC.
- `.github/workflows/publish-npm.yml` — `@sentinelqa/ts-runtime`
  to npm with provenance.
- `.github/workflows/publish-docker.yml` — `sentinelqa/runner` to
  Docker Hub for `linux/amd64` + `linux/arm64`.
- `.github/workflows/github-release.yml` — GitHub Release with
  the wheels + sdists + TS tarball as assets.

This is the runbook for an actual publish. It exists so the
owner can execute a release in one sitting with no surprises —
every command has a known exit code, every approval has a known
location in the GitHub UI, every artefact has a verify step.

The agent's standing authorisation for this repo covers PR
flow + CI watch + squash-merge. It explicitly **does not** cover
the operations in this runbook.

---

## Pre-flight

These checks gate the tag. If any check fails, stop the publish
and fix the underlying problem before retrying. `CLAUDE.md` §40
says "do not publish packages without explicit approval"; the
explicit approval is the signed block in
`docs/release/pre-1.0-review.md`.

### 1. Sign the pre-1.0 review

Open `docs/release/pre-1.0-review.md` and fill in the draft
sign-off block for the tag you're about to cut. For `v1.0.0`:

- [ ] **USPTO TM search** complete; verdict + date + screenshot URL recorded in `docs/dev/trademarks-and-naming.md`.
- [ ] **EUIPO TMview** search complete; verdict recorded.
- [ ] **UKIPO mark search** complete; verdict recorded.
- [ ] Every numeric gate (`make ci`, `make coverage`, `make test-full`, `make audit-metadata`, `make build-all`, `make inspect-all`) re-run on the tag commit and the actual numbers pasted into the sign-off block.
- [ ] Signature line filled in.

Commit the signed `pre-1.0-review.md` to `main` via a PR before
moving on. The act of signing this file is permission to **tag**,
not yet permission to publish.

### 2. Run every dry-run locally

Each registry has a paired dry-run that exercises the build +
validate path **without** publishing.

```bash
# PyPI: build every sdist + wheel, then `twine check --strict`.
uv run python -m scripts.release.dry_run_pypi --out-dir dist

# npm: build @sentinelqa/ts-runtime, pack, inspect the tarball,
# and run `npm publish --dry-run --access public`.
uv run python -m scripts.release.dry_run_npm --out-dir dist/npm

# Docker Hub: `docker buildx build --platform linux/amd64,linux/arm64 --no-push`.
# Requires Docker Desktop or docker-ce + buildx; on hosts that lack it
# the script exits 5 with a remediation hint.
uv run python -m scripts.release.dry_run_docker

# GitHub Release: confirm the CHANGELOG slice for the tag renders.
uv run python -m scripts.release.extract_release_notes v1.0.0 -o /tmp/release-notes.md
less /tmp/release-notes.md
```

Every dry-run must exit `0`. If any of them fails, stop — pushing
the tag will trigger the matching publish workflow, and the
workflow will fail the same way.

### 3. Confirm the GitHub Environments are wired

In `Settings → Environments` on `github.com/Ohswedd/sentinelqa`
verify each of the four publish environments exists and requires
manual approval from you:

- `pypi-release` (PyPI Trusted Publisher OIDC; no secret to store)
- `npm-release` (secret: `NPM_TOKEN`)
- `docker-release` (secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`)
- `github-release` (no secret — runs as the repo's default token)

For each environment: `Required reviewers = owner`, `Deployment
branches and tags = matching tags v*`.

The PyPI Trusted Publisher entry has to exist at
`https://pypi.org/manage/account/publishing/` for **every**
publishable Python package (`sentinelqa-cli`, `sentinelqa-engine`,
`sentinelqa-modules`, `sentinelqa-integrations`, `sentinelqa`,
`sentinelqa-mcp`). Fields: `Owner = Ohswedd`, `Repository
name = sentinelqa`, `Workflow filename = publish-pypi.yml`,
`Environment = pypi-release`.

---

## Tag

Once every pre-flight check is green, cut the tag from the
already-merged commit on `main`. The tag must be GPG-signed
(`CLAUDE.md` §3 — owner identity preserved).

```bash
# From a clean main on the commit that the pre-1.0-review block points at:
git checkout main
git pull --ff-only origin main

# Confirm the commit SHA matches the one in pre-1.0-review.md.
git log -1 --format="%H %s"

# Cut the signed tag.
git tag -s v1.0.0 -m "v1.0.0"

# Push the tag (this triggers all four publish workflows).
git push origin v1.0.0
```

Pushing the tag is the moment of no-return: the four publish
workflows start immediately, gated only on the per-environment
approvals you wired in step 3.

---

## Approve each publish

Watch `Actions` tab — four workflows queue against your environments:

1. **`Publish (PyPI)`** → click "Review deployments" → "Approve
   and deploy". Watch the `verify` job at the end install from
   PyPI and report `sentinel --version`.
2. **`Publish (npm)`** → same approval flow. Watch the `verify`
   job at the end poll `npm view @sentinelqa/ts-runtime@<tag>`
   until it returns the right version.
3. **`Publish (Docker Hub)`** → same approval flow. Watch the
   `verify` job at the end pull the image, assert the manifest
   carries `linux/amd64` + `linux/arm64`, and run `sentinel
--version` inside the image.
4. **`Publish (GitHub Release)`** → same approval flow. Confirm
   the release notes render correctly and every artefact
   (wheels + sdists + TS tarball) appears under "Assets".

If any verify job fails, **do not** retry the workflow. Yank
the just-published version per the
`docs/dev/semver.md#yanking-a-release` procedure and cut a new
patch.

---

## Verify

Once all four workflows are green, run the post-publish smoke
test against the live registries to confirm everything actually
works for an outside consumer:

```bash
SENTINELQA_TEST_POST_PUBLISH=1 \
  uv run pytest tests/integration/release/test_post_publish_smoke.py -v
```

The smoke test pip-installs from PyPI, npm-installs from npm,
pulls from Docker Hub, and runs `sentinel --version` against each
of them. The tag is read from `apps/cli/pyproject.toml` so it
stays accurate across future bumps.

---

## Announce

`docs/release/announcement-draft.md` ships four pre-written copy
variants (GitHub release notes, short post, HN/Lobsters seed,
blog seed). Pick the appropriate ones and post them yourself.
The agent does not post on your behalf.

---

## Watch (24 hours)

For the first 24 hours after a publish:

- Monitor `https://github.com/Ohswedd/sentinelqa/issues` for new
  bug reports.
- Monitor `https://pypi.org/project/sentinelqa-cli/` for download
  stats and yank requests.
- Monitor `https://hub.docker.com/r/sentinelqa/runner` for pull
  stats and reported issues.
- Keep the `docs/release/post-publish-incident.md` runbook open
  (created the first time we hit an actual post-publish issue).

If a critical post-publish issue surfaces:

1. Cut a fix on a branch off `main`; PR + merge; cut a patch tag
   (`v1.0.1`).
2. Yank the broken version on PyPI + npm (don't delete it; yanking
   preserves history).
3. Document the yank under the next patch's `### Removed` block
   in `CHANGELOG.md`.

---

## What this runbook explicitly does not authorise

- **The agent** never runs `git tag -s`, `twine upload`, `pnpm
publish`, `docker push`, or any equivalent. These are owner
  commands. (`CLAUDE.md` §3 + §40)
- **Tagging without signing the pre-1.0 review** is forbidden —
  the act of signing the review **is** the explicit owner
  authorisation that §40 requires.
- **Force-pushing a tag** is forbidden. If a tag goes out wrong,
  yank and cut the next patch.
- **Skipping the dry-runs** is forbidden. They are local and
  cheap; their job is to surface the broken state before the
  publish runs in CI.

---

# This is the only time SentinelQA actually publishes to the public registries. Read it twice before running.
