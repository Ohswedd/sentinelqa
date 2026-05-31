# Docs site deploy

Status: `Stable`

Authority: `CLAUDE.md` §34 (Documentation rules), `docs/adr/0032-docs-site.md` (Astro Starlight choice), `plans/phase-35-public-release/04-docs-site-deploy.md`.

The SentinelQA docs site (`apps/docs/`, Astro Starlight) deploys to **Cloudflare Pages** on every push to `main`, with **preview deploys** on every PR. This file is the operator runbook.

## TL;DR

- Production URL: <https://docs.sentinelqa.dev> (custom domain; CNAME → Pages project).
- Workflow: [`.github/workflows/docs-deploy.yml`](../../.github/workflows/docs-deploy.yml).
- Owner-provisioned secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT`.
- Fork PRs: secrets are unavailable; the workflow builds the site (proves it compiles) but skips the publish step with a clear notice.

## Provisioning (one-time, owner)

These steps are run **by the human owner** before the repo flips public (task 35.08). Until then, the workflow runs the build but skips the deploy step because the secrets are missing — that's intentional, not a failure.

### 1. Create the Cloudflare Pages project

```bash
# Once, from the owner's workstation. Requires `wrangler` and a Cloudflare account.
wrangler pages project create sentinelqa-docs --production-branch=main
```

### 2. Mint the API token (least privilege)

Create a Cloudflare API token with **only** these permissions:

- `Account` → `Cloudflare Pages` → `Edit`
- (optional, if you also use the same token for analytics): `Account` → `Analytics` → `Read`

Scope it to the SentinelQA account only. **Do not** grant Zone:Edit or any DNS-edit permission to this token — DNS is provisioned manually below.

### 3. Set the GitHub repository secrets

In `https://github.com/Ohswedd/sentinelqa/settings/secrets/actions`:

| Secret                     | Value                     | Notes                                    |
| -------------------------- | ------------------------- | ---------------------------------------- |
| `CLOUDFLARE_API_TOKEN`     | The token from step 2     | Owner-only, rotated quarterly.           |
| `CLOUDFLARE_ACCOUNT_ID`    | The Cloudflare account id | Found in the Cloudflare dashboard URL.   |
| `CLOUDFLARE_PAGES_PROJECT` | `sentinelqa-docs`         | Must match the project name from step 1. |

### 4. Point the custom domain at the project

In the Cloudflare dashboard, add the custom domain `docs.sentinelqa.dev` to the Pages project. Cloudflare provisions the TLS certificate via Universal SSL — no extra step required if `sentinelqa.dev` is already in the same Cloudflare account.

If the apex domain lives elsewhere, add a `CNAME` record:

```
docs    CNAME    sentinelqa-docs.pages.dev.    (TTL auto)
```

### 5. Verify

After the first push to `main` post-provisioning:

```bash
gh run watch -R Ohswedd/sentinelqa --workflow docs-deploy.yml
curl -fsSI https://docs.sentinelqa.dev | head -5
```

Both must return success. If the site 404s, the most common cause is a typo in `CLOUDFLARE_PAGES_PROJECT`.

## Preview deploys (PRs)

Every PR triggers the same workflow on the PR branch. Cloudflare Pages publishes the build under a preview URL of the form `https://<branch-slug>.sentinelqa-docs.pages.dev`. The workflow leaves an inline comment on the PR with the preview URL.

**Limitation (well-known):** Cloudflare Pages preview deploys do not work from forked PRs because GitHub does not expose repo secrets to PRs from forks. The workflow detects this case and skips the deploy step with a `::notice` line; the build itself still runs, so a fork PR proves the docs compile, just not that they publish. The owner can opt in to publish a fork preview by running `make docs-build` locally and pushing the dist to a temporary branch.

## What the workflow does

1. Checks out the repo at the triggering ref.
2. Installs `uv` + Python 3.12 with cache.
3. Installs all workspace Python deps (`uv sync --frozen --all-packages`) — required because `make docs-gen-all` runs Python generators.
4. Installs `pnpm` + Node 20 with cache.
5. Installs all workspace JS deps (`pnpm install --frozen-lockfile`).
6. Runs `make docs-build` — regenerates CLI / SDK / MCP / errors / ADR index pages, then runs `astro build`.
7. If the Cloudflare secrets are present, deploys `apps/docs/dist/` to the configured Pages project.
8. On PRs, comments the preview URL.

## Troubleshooting

- **`pnpm: command not found`** → `pnpm-lock.yaml` is missing or the lockfile is stale. Run `pnpm install` locally, commit the updated lockfile.
- **`make docs-gen-all` fails** → one of the Python generators is broken. Run `make docs-check-fresh` locally — it tells you which generator is out of sync.
- **`astro build` fails on link check** → a sidebar entry in `apps/docs/astro.config.mjs` points at a missing content file. Cross-check with `tests/integration/docs/test_docs_site_scaffold.py`.
- **Cloudflare returns 401** → the `CLOUDFLARE_API_TOKEN` was rotated; mint a new one and update the secret.
- **Custom domain shows the Cloudflare default page, not the build** → CNAME hasn't propagated. Wait 5 minutes, then re-check `dig docs.sentinelqa.dev CNAME +short`.

## Rollback

Cloudflare Pages keeps every deployment. To roll back:

```bash
wrangler pages deployment list --project-name=sentinelqa-docs
wrangler pages deployment promote <id> --project-name=sentinelqa-docs
```

There is no destructive operation here — the previous deploy is still online; promoting an older one swaps the production alias only.

## Related

- [`docs/adr/0032-docs-site.md`](../adr/0032-docs-site.md) — why Astro Starlight.
- [`docs/dev/ci-and-branch-protection.md`](./ci-and-branch-protection.md) — the broader CI surface.
- [`plans/phase-35-public-release/04-docs-site-deploy.md`](../../plans/phase-35-public-release/04-docs-site-deploy.md) — the task spec.
