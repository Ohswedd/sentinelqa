# Task 36.03 — npm publish workflow

## Deliverables

- `.github/workflows/publish-npm.yml`:
  - Trigger: `on: { push: { tags: ["v*"] } }`.
  - Job: builds `@sentinelqa/ts-runtime` via `pnpm --filter
    @sentinelqa/ts-runtime build` (already a Phase 04 script);
    publishes with `pnpm publish --access public --provenance`.
  - `provenance: true` is enabled (npm provenance via OIDC token).
  - Requires:
    - `NPM_TOKEN` secret with publish scope (owner provisions).
    - `id-token: write` permission on the job for OIDC provenance.
  - Verification step: `npm view @sentinelqa/ts-runtime version`
    after publish; fails on mismatch.
- `package.json` already has `private:true` removed at v1.0.0 (Phase
  36.01); `files:` whitelist verified to ship only `dist/`,
  `LICENSE`, `package.json`, `README.md`.
- `scripts/release/dry_run_npm.py` — runs `pnpm pack` + `npm publish
  --dry-run` and asserts the tarball does not contain `.git/`,
  `.env`, `node_modules/`, source maps, `.test.ts`.

## Tests required

- `tests/integration/release/test_npm_dry_run.py` — calls
  `scripts/release/dry_run_npm.py`; expects exit 0 on current `main`.

## Definition of Done

- [ ] Workflow committed.
- [ ] `private:true` removed; `files:` whitelist verified.
- [ ] Dry-run green.
- [ ] `STATUS.md` updated.
