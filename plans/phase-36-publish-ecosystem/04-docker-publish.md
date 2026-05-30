# Task 36.04 — Docker Hub multi-arch publish

## Deliverables

- `.github/workflows/publish-docker.yml`:
  - Trigger: `on: { push: { tags: ["v*"] } }`.
  - Uses `docker/setup-qemu-action` + `docker/setup-buildx-action` +
    `docker/build-push-action`.
  - Platforms: `linux/amd64`, `linux/arm64`.
  - Tags pushed: `sentinelqa/runner:<tag>` (e.g. `1.0.0`),
    `sentinelqa/runner:1.0`, `sentinelqa/runner:latest`, plus the
    full Git SHA pin (`sentinelqa/runner:sha-<short>`).
  - Build context: `apps/cli/sentinel/runner/docker/`.
  - Required secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` (owner
    provisions).
  - Post-push verify: `docker pull sentinelqa/runner:<tag>` and
    `docker run --rm sentinelqa/runner:<tag> sentinel --version`.
- `apps/cli/sentinel/runner/docker/Dockerfile.runner` — review:
  - Pinned base image (existing).
  - Multi-arch friendly (no x86-only binaries).
  - `LABEL org.opencontainers.image.source=...` / `.title` /
    `.licenses=Apache-2.0` / `.version=<built-arg>`.
- `scripts/release/dry_run_docker.py` — `docker buildx build
  --platform linux/amd64,linux/arm64 --no-push` ensures the build
  succeeds for both arches before the tag.

## Tests required

- `tests/integration/release/test_docker_dry_run.py` — calls the
  dry-run; gated by `SENTINELQA_HAS_DOCKER=1`.

## Definition of Done

- [ ] Workflow committed; multi-arch verified.
- [ ] OCI labels present.
- [ ] Dry-run green when Docker is available.
- [ ] `STATUS.md` updated.
