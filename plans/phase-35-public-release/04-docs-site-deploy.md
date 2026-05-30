# Task 35.04 — Docs site deploy (Cloudflare Pages)

## Deliverables

- New GitHub Actions workflow `.github/workflows/docs-deploy.yml`:
  - Triggered on push to `main`.
  - Runs `pnpm install --frozen-lockfile` + `make docs-build`.
  - Deploys `apps/docs/dist/` to Cloudflare Pages via the official
    `cloudflare/wrangler-action`.
  - Required secrets: `CLOUDFLARE_API_TOKEN`,
    `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT` — owner-
    provisioned, documented in `docs/dev/docs-deploy.md`.
- Preview deploys on every PR via the same workflow run from the PR
  branch (Cloudflare's `--branch` flag); preview URL posted as a PR
  comment by the existing `pr-comment` action.
- Custom domain: `docs.sentinelqa.dev` (placeholder; owner sets the
  DNS CNAME). Documented in `docs/dev/docs-deploy.md`.
- The README references the public URL (`https://docs.sentinelqa.dev`)
  with an `<!-- editorconfig: keep -->` marker so the lychee link
  check skips it until the DNS lands.
- If the secrets are missing on a fork PR, the deploy step is skipped
  with a clear log message (PR can't deploy from a fork — well-known
  Cloudflare-Pages limitation; documented).

## Tests required

- `tests/integration/docs/test_deploy_workflow.py` — workflow YAML
  validates against the GitHub-Actions schema.

## Definition of Done

- [ ] Workflow ships.
- [ ] `docs/dev/docs-deploy.md` documents the setup.
- [ ] README links to the public URL (gated on owner's DNS step).
- [ ] `STATUS.md` updated.
