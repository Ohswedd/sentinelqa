# Task 36.01 — v1.0.0 tag preparation

## Deliverables

- Bump every publishable manifest from `0.7.0` to `1.0.0`:
  - `apps/cli/pyproject.toml`
  - `engine/pyproject.toml`
  - `modules/pyproject.toml`
  - `integrations/pyproject.toml`
  - `packages/python-sdk/pyproject.toml`
  - `packages/mcp-server/pyproject.toml`
  - `packages/ts-runtime/package.json`
- `uv sync --frozen --all-packages` regenerates `uv.lock`.
- `make sdk-api-snapshot` regenerates `packages/python-sdk/api-snapshot.json`.
- `CHANGELOG.md` gets a curated `[1.0.0] - YYYY-MM-DD` section
  derived from `make changelog-draft FROM=v0.7.0 TO=HEAD`. Honest
  list — no marketing.
- `docs/dev/semver.md` tag-plan row for `v1.0.0` updated to reflect
  what shipped between v0.7.0 and v1.0.0 (Phases 30–35 all of them).
- `docs/release/pre-1.0-review.md` gets a fresh sign-off block draft
  for `v1.0.0` with every numeric gate pre-filled (same shape as the
  v0.7.0 draft block in Phase 28).
- `make build-all` produces 13 artifacts at 1.0.0; `make inspect-all`
  green.

## Tests required

- `tests/integration/release/test_v1_tag_prep.py` — every manifest
  reads `1.0.0`; api-snapshot is fresh; `make build-all` produces
  artifacts at the correct version.

## Definition of Done

- [ ] All six manifests + ts-runtime + Docker image (next task) at
      1.0.0.
- [ ] `CHANGELOG.md` `[1.0.0]` section curated.
- [ ] pre-1.0-review sign-off block draft for v1.0.0.
- [ ] `STATUS.md` updated.
