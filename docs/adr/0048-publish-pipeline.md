# ADR-0048: Publish pipeline (Phase 36)

## Status

Accepted

<!-- Date: 2026-06-01 -->
<!-- Authors: @ohswedd -->

## Context

Phase 36 closes the build plan with the first publication-eligible
tag (`v1.0.0`). Five distinct artefacts have to move from this
repository to public registries in lock-step on every future tag:

- six Python distributions (`sentinelqa`, `sentinelqa-cli`, `sentinelqa-engine`, `sentinelqa-modules`, `sentinelqa-integrations`, `sentinelqa-mcp`) to PyPI;
- one TypeScript distribution (`@sentinelqa/ts-runtime`) to npm;
- one Docker image (`sentinelqa/runner`) to Docker Hub, multi-arch (linux/amd64 + linux/arm64);
- one GitHub Release that ties them together with curated release notes and the built artefacts as assets.

The constraints that frame this decision:

- §3 (Ownership) — the agent **never** publishes; every push to a public registry is an owner action.
- §40 (Versioning & release rules) — explicit owner go-ahead is required before any tag is publication-eligible; package contents must be inspected; tests must pass; secrets cannot leak.
- §41 (Privacy & telemetry) — no telemetry call-home in the published artefacts.

The pipeline must therefore be:

- Triggered by a single observable event (`v*` tag push).
- Reproducible locally via dry-runs.
- Gated by GitHub Environments so the owner authorises each push one registry at a time.
- Auditable — every artefact carries provenance metadata.
- Tied to `CHANGELOG.md` so release notes are curated, not auto-generated.

The first six tags (`v0.1.0`..`v0.7.0`) are retrospective and were
not published; `v1.0.0` is the first publication-eligible tag and
the first artefact this pipeline has to ship for real.

## Decision

Four independent GitHub Actions workflows triggered on the same
`v*` tag push, each gated on its own owner-approval environment:

| Workflow                               | Environment      | Notes                                                                  |
| -------------------------------------- | ---------------- | ---------------------------------------------------------------------- |
| `.github/workflows/publish-pypi.yml`   | `pypi-release`   | Trusted-Publisher OIDC. No long-lived token. `skip-existing: false`.   |
| `.github/workflows/publish-npm.yml`    | `npm-release`    | `pnpm publish --access public --provenance`. Slot via OIDC.            |
| `.github/workflows/publish-docker.yml` | `docker-release` | Multi-arch buildx + QEMU. provenance + SBOM on. Four tags per release. |
| `.github/workflows/github-release.yml` | `github-release` | `softprops/action-gh-release@v2`. Body from extracted CHANGELOG.       |

Each workflow exposes a matching local dry-run that the owner runs
before pushing the tag:

| Workflow             | Dry-run script                                                                                        |
| -------------------- | ----------------------------------------------------------------------------------------------------- |
| `publish-pypi.yml`   | `scripts/release/dry_run_pypi.py` (build + `twine check --strict`)                                    |
| `publish-npm.yml`    | `scripts/release/dry_run_npm.py` (build + `pnpm pack` + `npm publish --dry-run` + tarball inspection) |
| `publish-docker.yml` | `scripts/release/dry_run_docker.py` (`docker buildx build --platform amd64,arm64 --no-push`)          |
| `github-release.yml` | `scripts/release/extract_release_notes.py` (CHANGELOG slicer)                                         |

The runbook at `docs/release/publish-runbook.md` is the single
owner-facing document that drives an actual publish:

1. Sign the `v1.0.0` block of the pre-tag review process (trademark rows + signature).
2. Run all four dry-runs locally.
3. `git tag -s v1.0.0`; `git push origin v1.0.0`.
4. Approve each of the four publish workflows in the GitHub Environments UI as they trigger.
5. Run the post-publish smoke (`SENTINELQA_TEST_POST_PUBLISH=1` - `tests/integration/release/test_post_publish_smoke.py`).
6. Post the announcement drafts from `docs/release/announcement-draft.md`.
7. Watch the registries for 24 h.

The agent's standing authorization for this repo (push branches,
open PRs, watch CI, squash-merge) **does not** extend to `git tag
-s` / `twine upload` / `pnpm publish` / `docker push`. Those are
owner commands explicitly forbidden by our engineering rules+ §40.

The `sentinelqa/runner` Docker image is built from a new
Dockerfile (`apps/cli/sentinel/runner/docker/Dockerfile.publish`)
that installs `sentinelqa-cli==<tag>` from PyPI into a dedicated
venv at `/opt/sentinelqa`. The existing
`Dockerfile.runner` (Phase 08, the bind-mount runner used by
`sentinel test --docker`) stays as-is.

## Consequences

- **Positive:** - One mental model per registry — workflow + dry-run + verify - environment + secret. - Provenance everywhere (PyPI Trusted Publisher, npm `--provenance`, Docker `provenance: true` + `sbom: true`). - The owner can validate every artefact locally before the tag is irrevocable. - The runbook lists exactly which commands the human runs and which they delegate to GitHub; the agent never publishes.
- **Negative / trade-off:** - Four independent workflows mean four independent failure surfaces; a partial publish (PyPI green, npm red) is possible. We accept that — the runbook's "watch" step covers it and a yank can recover via the `docs/dev/semver.md` yanking procedure. - The Docker image is its own attack surface: any compromise of the PyPI install at image-build time is baked into the image. We accept that because the image bakes the install from the just-published wheel and the publish workflow only runs against approved environments.
- **Follow-up obligations:** - Trusted-Publisher / npm / Docker Hub / GitHub credentials must be configured on the org before the first publish. These are documented in the runbook; they are owner actions, not agent actions. - The four publish workflows are not listed in `docs/dev/branch-protection.md`'s required-check matrix because they only fire on tag pushes, not PRs.

## Alternatives considered

- **Single mega-workflow.** Rejected — one approval gate per registry forces a per-registry decision, which matches how the owner thinks about ROI vs risk. A single workflow would either require a single approval that authorises every registry simultaneously (too coarse) or four sequential approvals inside one job (too implicit).
- **Auto-tag from `main` after CI is green.** Rejected — the our engineering rules authorisation. Auto-tagging would couple "tests pass" with "ship to the world", and they are not the same decision.
- **Use long-lived PyPI / npm tokens.** Rejected — PyPI Trusted Publisher (OIDC) and npm `--provenance` (OIDC) are both stable in 2026 and avoid storing high-blast-radius secrets in the repo. The only registry without an OIDC option today is Docker Hub, which still uses an account access token (rotatable; scoped per-repo).
- **Skip Docker Hub.** Rejected — the Phase 08 Playwright runner image is a stated PRD deliverable (our product spec ADR-0013); shipping it as the published `sentinelqa/runner` closes that loop.

## References

- our engineering rules(Ownership), §40 (Versioning & release rules), §41 (Telemetry).
- `docs/dev/semver.md` (tag plan; `v1.0.0` row).
- the pre-tag review process (sign-off contract).
- `docs/release/publish-runbook.md` (the runbook this ADR authorises).
- (per-task specs).
- ADR-0013 (Docker runner pinning).
- ADR-0028 (Versioning & release prep).
- ADR-0047 (Public release readiness — what this ADR builds on).
