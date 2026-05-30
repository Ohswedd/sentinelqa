# Task 35.05 — Brand assets

## Deliverables

- `docs/assets/brand/`:
  - `logo.svg` — primary mark (placeholder design; owner can replace).
  - `logo-256.png`, `logo-512.png`, `logo-1024.png`.
  - `social-preview-1280x640.png` — GitHub social preview card.
  - `favicon.svg`, `favicon-16.png`, `favicon-32.png`,
    `apple-touch-icon-180.png`.
- `docs/dev/brand.md` — brand-usage guidance: SentinelQA name as
  trademark; usage rules; what NOT to do.
- The Astro Starlight site (`apps/docs/`) wires the favicon set into
  its `<head>`; social-preview wired into `<meta name="og:image">` and
  Twitter card.
- The README references `docs/assets/brand/social-preview-1280x640.png`
  in the GitHub repo's "Social preview" setting (owner uploads).

## Tests required

- `tests/integration/docs/test_brand_assets.py` — every referenced
  brand asset path exists; favicons are valid PNG/SVG.

## Definition of Done

- [ ] All assets ship.
- [ ] `docs/dev/brand.md` documents usage rules.
- [ ] `STATUS.md` updated.
