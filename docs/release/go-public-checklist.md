# Go-public pre-flight checklist (OWNER-GATED)

Status: `Stable`

Authority: `CLAUDE.md` §3 (Repository privacy + ownership),
`plans/phase-35-public-release/08-go-public.md`.

This file is the **owner's** pre-flight checklist before flipping
`Ohswedd/sentinelqa` from `private` to `public`. The agent prepared
every artifact this list references; the **flip itself is done by
the human owner** and is not in the agent's authorization scope
(`CLAUDE.md` §3).

The repo stays private until **every** row below is ticked and the
sign-off block at the bottom is filled in.

## 1. Engineering gates

- [ ] Phase 35 closed: every task (35.01–35.08) has a signed
      gate-review row in [`plans/STATUS.md`](../../plans/STATUS.md).
- [ ] `make ci` is green on `main` (paste the local summary line under
      the sign-off).
- [ ] `make test-full` is green on `main` (includes slow / property
      tests).
- [ ] `make coverage` reports ≥ 95 % on `main`.
- [ ] `make audit-license-headers` is green on `main`.
- [ ] `make audit-metadata` is green on `main`.
- [ ] `make docs-build` succeeds; `make docs-check-fresh` is green.

## 2. Pre-1.0 review for v0.7.0

- [ ] [`docs/release/pre-1.0-review.md`](./pre-1.0-review.md) is
      signed for `v0.7.0`, **including** the registered-marks lanes
      (USPTO / EUIPO / UKIPO verdict rows).
- [ ] `v0.7.0` tag exists on `origin/main` (or the owner has approved
      tagging it during the flip).

## 3. Secret + privacy hygiene

- [ ] `gitleaks detect --no-git --redact` over the full working tree
      is clean (post-Phase-29 baseline holds).
- [ ] No `.env`, `.env.local`, `~/.aws/`, `~/.config/`,
      `*.private-key`, or PEM files in the tree.
- [ ] `git log --grep "Co-authored-by:" v0.0.0..HEAD` returns zero AI
      co-author trailers (`CLAUDE.md` §3).
- [ ] `tests/security/test_no_stealth_flags.py` and the related
      safety-boundary tests are green.

## 4. ADRs + documentation

- [ ] Every ADR under [`docs/adr/`](../adr/) is `Accepted` or
      `Superseded` (no `Draft`).
- [ ] `PRD.md` reflects the shipped behavior; no unresolved
      "**LIVE**" / "**TODO**" markers.
- [ ] `CLAUDE.md` reflects the current engineering rules.
- [ ] [`plans/STATUS.md`](../../plans/STATUS.md)'s deferred-scope
      register is empty.

## 5. Public-surface readiness

- [ ] [`README.md`](../../README.md) is the polished
      v0.7.0 cover letter (Phase 35.01).
- [ ] [`SECURITY.md`](../../SECURITY.md) ships the private-disclosure
      path (Phase 35.02).
- [ ] [`.github/CODE_OF_CONDUCT.md`](../../.github/CODE_OF_CONDUCT.md)
      adopts Contributor Covenant 2.1 (Phase 35.02).
- [ ] `.github/ISSUE_TEMPLATE/*.yml` and
      `.github/pull_request_template.md` are present (Phase 35.02).
- [ ] [`NOTICE`](../../NOTICE) attributes every vendored upstream
      (Phase 35.03).
- [ ] [`.github/dependabot.yml`](../../.github/dependabot.yml) covers
      all four ecosystems (Phase 35.07).
- [ ] Brand assets under
      [`docs/assets/brand/`](../assets/brand/) and the docs-public
      copies are present (Phase 35.05).
- [ ] Docs deploy workflow at
      [`.github/workflows/docs-deploy.yml`](../../.github/workflows/docs-deploy.yml)
      and operator doc at
      [`docs/dev/docs-deploy.md`](../dev/docs-deploy.md) are present
      (Phase 35.04).
- [ ] Branch-protection spec at
      [`docs/dev/branch-protection.md`](../dev/branch-protection.md)
      and the verifier at
      [`scripts/release/verify_branch_protection.py`](../../scripts/release/verify_branch_protection.py)
      are present (Phase 35.06).

## 6. Announcement

- [ ] [`docs/release/announcement-draft.md`](./announcement-draft.md)
      reviewed by the owner; final copy approved.

## 7. The flip (owner-only)

After every checkbox above is ticked, the owner runs these commands
from their workstation. **Do not run these as the agent.** They are
documented for the operator's convenience.

```bash
# 1. Flip visibility.
gh repo edit Ohswedd/sentinelqa --visibility public

# 2. Set the public-facing description + homepage.
gh repo edit Ohswedd/sentinelqa \
  --description "Playwright-native release-confidence engine for LLM-built apps"
gh repo edit Ohswedd/sentinelqa --homepage "https://docs.sentinelqa.dev"

# 3. Add discovery topics.
gh repo edit Ohswedd/sentinelqa \
  --add-topic playwright \
  --add-topic llm \
  --add-topic testing \
  --add-topic qa \
  --add-topic ai \
  --add-topic security \
  --add-topic release-confidence
```

## 8. Post-flip (owner-only)

After the flip, in this order:

1. Upload the social-preview PNG via
   `Settings → General → Social preview → Upload an image`
   (file: `docs/assets/brand/social-preview-1280x640.png`).
2. Enable Private Vulnerability Reporting:
   `Settings → Code security and analysis → Private vulnerability reporting → Enable`.
3. Apply the branch-protection rules from
   [`docs/dev/branch-protection.md`](../dev/branch-protection.md)
   via the GitHub UI (or `gh api -X PUT
   repos/Ohswedd/sentinelqa/branches/main/protection -f …` once the
   payload is reviewed). Then run:

   ```bash
   make verify-branch-protection
   ```

   …and confirm exit 0.
4. Confirm the docs site is reachable at
   <https://docs.sentinelqa.dev>:

   ```bash
   curl -fsSI https://docs.sentinelqa.dev | head -5
   ```

5. Add a tag-protection ruleset for `v*`:
   `Settings → Tags → New ruleset` with the rules in
   [`docs/dev/branch-protection.md`](../dev/branch-protection.md)
   "Tag protection" section.

## Sign-off

| Field | Value |
|---|---|
| Owner | _to be filled in by the human owner_ |
| Date | _YYYY-MM-DD_ |
| `make ci` summary | _paste the final line_ |
| Tag at flip | _e.g. `v0.7.0`_ |
| Pre-1.0 review row signed | _yes / no_ |

> The act of signing this file is **permission to flip visibility**;
> it is NOT permission to publish packages. PyPI / npm / Docker Hub
> publication lives in Phase 36 and requires its own owner sign-off
> per [`docs/release/pre-1.0-review.md`](./pre-1.0-review.md).
