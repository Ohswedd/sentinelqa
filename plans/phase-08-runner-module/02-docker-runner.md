# Task 08.02 — Docker runner

## Objective

Run tests inside a deterministic container image so CI behavior matches local behavior.

## Deliverables

- `apps/cli/sentinel/runner/docker/Dockerfile.runner` — based on `mcr.microsoft.com/playwright:v<version>-jammy`, pinned to the Playwright version used in `packages/ts-runtime`.
- `engine/runner/docker.py` exposing `DockerRunner.run(...)` with the same contract as `LocalRunner`.
- Mounts: project source read-only, `<run-dir>` writable.
- Networking: defaults to a private bridge; allows access to `host.docker.internal` for local target URLs.
- Image tag includes Playwright version; pulled from a registry the user controls.
- Runner gates on safety policy before launching the container.

## Steps

1. Author the Dockerfile pinned to Playwright + Node versions.
2. Add `make build-runner-image` to build locally.
3. Implement `DockerRunner` using `docker` CLI or `docker-py`; prefer subprocess for portability.
4. Plumb config through env vars.
5. Add CI step that builds the image once (cached) and runs the fixture suite.

## Acceptance criteria

- `DockerRunner` runs the fixture suite inside the container.
- Versions pinned; image rebuild reproducible.

## Tests required

- `tests/integration/runner/test_docker_runner.py` (skipped if Docker unavailable; CI must run it).

## PRD / CLAUDE.md references

- PRD §9.4, §11.
- CLAUDE.md §8.

## Definition of Done

- [ ] Image builds and runs the fixture suite.
- [ ] Versions pinned.
- [ ] `STATUS.md` updated.
