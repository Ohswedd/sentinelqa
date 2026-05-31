# Brand usage

Status: `Stable`

Authority: `plans/phase-35-public-release/05-brand-assets.md`,
`CLAUDE.md` §42 (Competitor awareness), `docs/dev/trademarks-and-naming.md`.

This page documents how the SentinelQA name, mark, and assets may be
used. The current mark is a **placeholder** by design — the human owner
replaces it with the registered mark before the `v1.0.0` publish
(`docs/release/pre-1.0-review.md`).

## Assets

The canonical brand assets live in [`docs/assets/brand/`](../assets/brand/).
The docs site (`apps/docs/`) carries the subset that needs to be
served (favicons + the social-preview OG image) in
[`apps/docs/public/`](../../apps/docs/public/).

| Asset                 | Path                                            | Notes                                                      |
| --------------------- | ----------------------------------------------- | ---------------------------------------------------------- |
| Primary mark (vector) | `docs/assets/brand/logo.svg`                    | Source of truth. 1:1 viewBox; crops cleanly to icon sizes. |
| Primary mark @ 256    | `docs/assets/brand/logo-256.png`                | RGBA. README / Slack / chat embeds.                        |
| Primary mark @ 512    | `docs/assets/brand/logo-512.png`                | App stores, Open Graph.                                    |
| Primary mark @ 1024   | `docs/assets/brand/logo-1024.png`               | Print, conference assets.                                  |
| Favicon (vector)      | `docs/assets/brand/favicon.svg`                 | Served at `/favicon.svg`.                                  |
| Favicon 16            | `docs/assets/brand/favicon-16.png`              | Browser tab.                                               |
| Favicon 32            | `docs/assets/brand/favicon-32.png`              | Browser tab @2x.                                           |
| Apple touch icon      | `docs/assets/brand/apple-touch-icon-180.png`    | iOS / iPadOS home-screen.                                  |
| Social preview        | `docs/assets/brand/social-preview-1280x640.png` | GitHub social card + OG image.                             |

All PNGs are generated procedurally from
[`scripts/release/gen_brand_pngs.py`](../../scripts/release/gen_brand_pngs.py).
The script is deterministic (same Pillow version → byte-identical
output) so the generated files are safe to commit. Re-run after
changing the source design:

```bash
uv run python -m scripts.release.gen_brand_pngs
```

## Naming

- The product name is **SentinelQA** — one word, capitalised S and Q.
  Not "Sentinel QA", not "Sentinelqa", not "sentinel-qa".
- The CLI executable is `sentinel` (lowercase).
- Package names: `sentinelqa-cli` (PyPI, Phase 36), `sentinelqa` (PyPI
  SDK), `@sentinelqa/*` (npm scope), `sentinelqa/runner` (Docker Hub).

## What you may do

You **may**, without asking:

- Link to SentinelQA, the docs site, and the GitHub repo.
- Use the logo and the name in articles, blog posts, talks, and
  comparison tables — including critical coverage — as long as the
  use does not imply endorsement.
- Include the logo in screenshots that show SentinelQA actually
  running.
- Use the social-preview card on social media when sharing
  SentinelQA news.

## What requires permission

You **may not**, without written permission from the owner:

- Use the SentinelQA name or logo on a competing product.
- Use the name or logo in a way that suggests endorsement, sponsorship,
  or an official partnership when none exists.
- Modify the mark (recolor, distort, animate, combine with other
  marks) beyond proportional scaling.
- Register the SentinelQA name, logo, or anything confusingly similar
  as your own trademark in any jurisdiction.
- Use the mark on merchandise (apparel, stickers, etc.) you sell.

Contact: `brand@sentinelqa.dev` (owner-provisioned inbox; placeholder
until the public flip).

## Pre-1.0 status

Until `v1.0.0`, the mark and the trademark posture are both
**provisional**:

- The mark is a placeholder design (a generic shield + monogram).
  The owner replaces it with the registered mark per
  `docs/release/pre-1.0-review.md` ("Trademarks" section).
- The trademark search lanes (USPTO / EUIPO / UKIPO) are documented
  in [`docs/dev/trademarks-and-naming.md`](./trademarks-and-naming.md);
  the registered-marks lanes remain open until owner sign-off.

If you spot a conflict — another product, package, or domain using
"SentinelQA" or a confusingly similar name — open a private issue via
[`SECURITY.md`](../../SECURITY.md) (so the owner can triage the
trademark exposure before it becomes public).

## Verification

The presence and integrity of every brand asset is pinned by
[`tests/integration/docs/test_brand_assets.py`](../../tests/integration/docs/test_brand_assets.py).
Missing or corrupt assets fail CI.

## Related

- `docs/dev/trademarks-and-naming.md` — trademark posture + search lanes.
- `docs/release/pre-1.0-review.md` — pre-1.0 sign-off checklist
  (includes "trademarks" rows the owner signs before any publish).
- `apps/docs/astro.config.mjs` — `head` section wires the favicons +
  Open Graph + Twitter Card images.
