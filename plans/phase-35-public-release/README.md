# Phase 35 — Public Release Engineering

## Objective

Turn the (until now private) `Ohswedd/sentinelqa` repository into a
public, professional, contributor-friendly project. Polish the README,
add the standard GitHub community files, audit licenses + headers,
configure branch protection and security advisories, and wire the
public docs site to a hosted preview (Cloudflare Pages or Vercel) so
contributors can read the docs without cloning.

The repository going public is OWNER-GATED (CLAUDE.md §3). This phase
prepares everything so the flip is one `gh repo edit --visibility public`
command at the end.

## PRD / CLAUDE.md references

- PRD §28 (Differentiation — Messaging), §32 (Recommended build order
  — public ship is the last bullet).
- CLAUDE.md §3 (Repository privacy + ownership), §34 (Documentation
  rules), §40 (Versioning + release rules), §42 (Competitor awareness).

## Sub-phases & tasks

1. `01-readme-polish.md` — Pre-1.0 public-facing `README.md` with
   badges, install/quickstart, demo GIF, "what is SentinelQA"
   one-paragraph pitch, links to the docs site.
2. `02-github-templates.md` — `.github/ISSUE_TEMPLATE/`,
   `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODE_OF_CONDUCT.md`,
   `SECURITY.md`, `CONTRIBUTING.md` polish.
3. `03-license-headers-audit.md` — Verify every shipped Python /
   TypeScript file declares SPDX-License-Identifier or is covered by
   the root `LICENSE`. Add headers where missing. Update `NOTICE`.
4. `04-docs-site-deploy.md` — Wire the Phase 27 Astro Starlight site
   to Cloudflare Pages (or Vercel) on every `main` push. Public URL
   recorded in `README.md`.
5. `05-brand-assets.md` — Project logo (SVG + 256/512/1024 PNG),
   GitHub social preview, favicon set. Brand-usage page in
   `docs/dev/brand.md`.
6. `06-branch-protection.md` — `main` requires PR + green CI;
   `CODEOWNERS` updated; signed commits encouraged; pre-receive hook
   wording.
7. `07-security-advisories.md` — Enable GitHub Security Advisories;
   `SECURITY.md` describes the private-disclosure path; pre-populate
   `.github/dependabot.yml` for Python + npm + GitHub Actions.
8. `08-go-public.md` — Owner-gated. Pre-flight checklist; flip
   visibility; update the docs site links; tweet/announce drafts.

## Definition of Done

- README is the cover letter of the project — short, accurate, no
  hype, no fake demo links.
- Every required GitHub community file ships and follows the GitHub
  community standards (the repo earns the "Community Standards" 100 %
  badge).
- License headers verified everywhere; `NOTICE` lists every vendored
  dep.
- Docs site builds clean and is served at the public URL.
- Branch protection rules documented (owner applies).
- ADR-0047 (Public release readiness) accepted.

## Phase Gate Review

- [ ] README + GH templates + license + docs site verified.
- [ ] Branch protection + Dependabot configured.
- [ ] Pre-flight checklist in `docs/release/go-public-checklist.md`
      complete.
- [ ] ADR-0047 accepted.
- [ ] Repo is **not yet public** — task 35.08 is the flip, gated on
      owner go-ahead.
- [ ] `STATUS.md` updated.
