# Task 36.06 — Post-publish smoke tests

## Deliverables

- `tests/integration/release/test_post_publish_smoke.py` (slow tier,
  gated by `SENTINELQA_TEST_POST_PUBLISH=1`):
  1. `uv pip install --index-url https://pypi.org/simple
     sentinelqa-cli==<tag>` into a fresh venv; runs `sentinel
     --version`; asserts version matches the tag.
  2. `pnpm install @sentinelqa/ts-runtime@<tag>` into a fresh project;
     runs `node -e "require('@sentinelqa/ts-runtime')"`; asserts
     import succeeds.
  3. `docker pull sentinelqa/runner:<tag>` + `docker run --rm
     sentinelqa/runner:<tag> sentinel --version`; asserts version
     matches.
  4. `docker pull sentinelqa/runner:<tag>` + `docker manifest
     inspect sentinelqa/runner:<tag>`; asserts both `linux/amd64`
     and `linux/arm64` are present.
- The test reads the `<tag>` from `apps/cli/pyproject.toml`'s
  version so it stays accurate.
- Test runs both:
  - During Phase 36 dry-run (against the staging tag); and
  - In the publish-runbook's "verify" step (against the real public
    artifacts).

## Tests required

- (the file itself is the test).

## Definition of Done

- [ ] Smoke test green against the local dist/ before the actual
      publish.
- [ ] Smoke test gated; not in default `make ci`.
- [ ] `STATUS.md` updated.
