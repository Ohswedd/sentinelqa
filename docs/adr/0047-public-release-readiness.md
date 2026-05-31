# ADR-0047: Public release readiness (Phase 35)

## Status

Accepted

<!-- Date: 2026-05-31 -->
<!-- Authors: @ohswedd -->

## Context

Phases 00–34 produced a feature-complete MVP plus the first four
ecosystem phases (multi-provider LLM, browser-auth, extended security
catalog, supply-chain audit, compliance packs). Until Phase 35 the
repository stayed private (`CLAUDE.md` §3) and only carried internal-
facing docs.

Going public is one decision the codebase has to back with multiple
artifacts at once:

- A README that doubles as the project cover letter — no marketing
  fluff, no fake demo links, every claim backed by a real doc page.
- The GitHub "Community Standards" set: structured issue forms, PR
  template, Contributor Covenant, `SECURITY.md` with a private
  disclosure path, `CONTRIBUTING.md` polish.
- License-header + NOTICE audit so vendored upstreams are properly
  attributed and source files carry SPDX where they're not implicitly
  covered by the root LICENSE.
- A docs deploy pipeline that publishes Astro Starlight to
  Cloudflare Pages on every `main` push and previews PRs.
- Brand assets — placeholder design now, registered mark before
  `v1.0.0` publish.
- Machine-checkable branch-protection spec + a `make verify-branch-
protection` script that diffs live GitHub state against the spec.
- A Dependabot config covering Python (uv-lockfile), npm, GitHub
  Actions, and the Docker runner image, plus a security policy
  documenting the disclosure timeline and the supported-versions
  matrix.
- A go-public pre-flight checklist that the human owner ticks before
  flipping visibility, with the flip commands documented but **not**
  executed by the agent (`CLAUDE.md` §3 — repo visibility is owner-
  only).

The decision in this ADR is how those concerns compose into one
phase's worth of artifacts, and which behaviors stay owner-gated.

## Decision

Phase 35 lands eight artifacts plus their tests, in this shape:

1. **README.md** — pre-1.0 public-facing cover letter, < 250 lines,
   buzzword-blocked by
   `tests/integration/docs/test_readme_links.py`. Includes a static
   terminal SVG (`docs/assets/demo-audit.svg`) as the demo asset; we
   intentionally do NOT ship an animated GIF that could rot when the
   CLI output format shifts.
2. **GitHub community files** — YAML issue forms
   (`bug_report.yml`, `feature_request.yml`,
   `security_disclosure.yml` whose body is a redirect to the private
   channel), `ISSUE_TEMPLATE/config.yml` disabling blank issues +
   surfacing the private security path, `SECURITY.md` with a
   coordinated-disclosure policy, `CODE_OF_CONDUCT.md` adopting
   Contributor Covenant 2.1 **by reference** (full text upstream).
3. **License headers + NOTICE audit** — directory-prefix coverage
   (root LICENSE covers `engine/`, `apps/`, `modules/`, `integrations/`,
   `packages/`, `scripts/`, `tests/`); SPDX headers required outside
   those prefixes; foreign SPDX inside the trees fails as drift.
   NOTICE attributes every vendored upstream at
   `packages/shared-schema/external/`.
4. **Docs deploy** — `.github/workflows/docs-deploy.yml` runs `make
docs-build` and publishes via `cloudflare/wrangler-action`. Fork
   PRs can't read deploy secrets, so the workflow detects missing
   `CLOUDFLARE_API_TOKEN` and skips the deploy step with a GitHub
   `::notice` line instead of failing.
5. **Brand assets** — placeholder design at `docs/assets/brand/`
   (SVG source + procedurally generated PNGs from
   `scripts/release/gen_brand_pngs.py`). Astro `head` wires
   favicons + Open Graph + Twitter Card image. The owner replaces
   the placeholder with the registered mark before publish.
6. **Branch protection** — `docs/dev/branch-protection.md` is the
   machine-checkable spec; `scripts/release/verify_branch_
protection.py` (+ `make verify-branch-protection`) diffs the
   live GitHub config against the spec. Read-only — the script
   never mutates GitHub state.
7. **Security advisories + Dependabot** — `.github/dependabot.yml`
   covers four ecosystems (Python via uv-lockfile, npm via pnpm-
   lockfile, GitHub Actions, the Docker runner image) on a weekly
   cadence. `docs/dev/security-policy.md` documents the supported-
   versions matrix, CVSS v4.0 bands, and the 90-day coordinated
   disclosure timeline.
8. **Go-public pre-flight** — `docs/release/go-public-checklist.md`
   is an owner-runnable checklist; the visibility-flip commands
   sit inside a fenced code block (documentation, not action).
   `docs/release/announcement-draft.md` ships four copy variants
   the owner adapts at flip time.

The **flip itself remains owner-gated** (`CLAUDE.md` §3). The agent
ships every artifact the owner needs, but the `gh repo edit
--visibility public` command is never executed by the agent. The
go-public checklist test pins this: it confirms the flip command
lives inside a fenced code block, not in an action path.

## Consequences

### Better

- The repo can flip to public without rushing — every artifact the
  owner needs is in place, machine-checked, and pinned by tests.
- The "Community Standards 100 %" badge is automatic once the repo
  is public (every required file ships and is shape-tested).
- Drift in branch-protection, license headers, NOTICE attribution,
  Dependabot coverage, or the announcement copy is caught by the
  Phase-35 test suite.
- The Cloudflare-Pages deploy is hermetic on fork PRs (no deploy
  step runs without secrets); the build still proves the docs
  compile so fork contributors get useful CI feedback.

### Worse

- Several artifacts hold owner-provisioned placeholders
  (`security@sentinelqa.dev`, `conduct@sentinelqa.dev`,
  `brand@sentinelqa.dev`, PGP fingerprint, the brand mark). Until
  the owner resolves each, the inbound channels are not yet live.
- The brand mark is procedurally rendered placeholder geometry;
  it must be replaced before `v1.0.0` publish.
- The branch-protection verifier depends on `gh` being installed
  and authenticated; CI cannot verify against a private repo.

### Accepted cost

- Two ecosystems we deliberately do NOT auto-update: the engine /
  modules / integrations Python manifests (covered transitively by
  the four pinned `pip` entries), and the docs site lockfile
  (changes there should land alongside docs-build edits, not as
  Dependabot drive-bys).
- The PR template was already strong; Phase 35.02 only pins its
  invariants via test rather than rewriting it.

## Alternatives considered

- **A single mega-PR per artifact.** Rejected — each Phase-35 task is
  cleanly separable; merging them as separate commits inside the same
  phase branch keeps history readable and lets the owner roll back a
  single artifact (e.g. the brand mark) without unwinding the rest.
- **Bundle license headers + NOTICE into Phase 36.** Rejected — the
  audit must be in place BEFORE the repo is public; foreign SPDX
  drift slipping into a public repo is a worse failure mode than a
  delayed flip.
- **Skip the docs-deploy workflow.** Rejected — without
  `docs.sentinelqa.dev` resolving on flip day, the README's docs-site
  link breaks and the announcement copy reads as aspirational.

## Related decisions

- ADR-0032 (Docs site choice — Astro Starlight) — the deploy workflow
  builds on this.
- ADR-0042..0046 (Phase 30–34 ecosystem expansion) — all referenced
  in the README module surface table.

## References

- `CLAUDE.md` §3 (Repository privacy + ownership) — gates the
  visibility flip.
- `CLAUDE.md` §34 (Documentation rules) — drives the README, docs
  site, status labels, and ADR triggers.
- `CLAUDE.md` §40 (Versioning + release rules) — frames the
  supported-versions policy in `docs/dev/security-policy.md`.
- `CLAUDE.md` §42 (Competitor awareness) — frames the brand-usage
  doc.
- `plans/phase-35-public-release/` — task spec for every Phase-35
  artifact.
- `docs/release/pre-1.0-review.md` — sign-off contract for tags;
  Phase 35.08 references the v0.7.0 row.
- `docs/dev/semver.md` — supported-versions policy that the security
  policy doc inherits from.
