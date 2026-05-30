<!-- GitHub release-notes template for SentinelQA.

     Copy this file into the GitHub release body when cutting a tag, then fill
     in the placeholders. The drafted CHANGELOG.md section is the source-of-
     truth for the entries; this template adds the upgrade-and-context framing
     a release reader expects.

     Drafting workflow:
       1. `make changelog-draft` → CHANGELOG.draft.md (uses scripts/release/draft_changelog.py).
       2. Curate CHANGELOG.draft.md by hand (drop noise, merge near-duplicates,
          surface BREAKING CHANGEs, group bullets logically).
       3. Move the new section into CHANGELOG.md ABOVE the previous section.
       4. Copy the curated section into this template and fill in the rest.
       5. Open a PR per `docs/dev/semver.md`; tag once merged.
-->

# SentinelQA vX.Y.Z

_Status: pre-1.0 — see [`docs/dev/semver.md`](docs/dev/semver.md)._

## Summary

<!-- Two-to-four sentences. What did we ship in this version and what does it
     unlock for users (`Can this software be trusted enough to ship?` — CLAUDE.md §45). -->

## Highlights

- <!-- The 3–5 most user-visible changes. -->

## Upgrade notes

<!-- Anything a user must do when moving from the previous version. If empty,
     write "No action required." -->

- Python: `pip install --upgrade sentinelqa sentinelqa-cli`.
- npm: `pnpm add -D @sentinelqa/ts-runtime@X.Y.Z`.
- Docker (runner): `docker pull sentinelqa-runner:X.Y.Z`.

## Breaking changes

<!-- Required when bumping major (post-1.0) or when the pre-1.0 minor introduces
     a documented break (see docs/dev/semver.md §"Pre-1.0 rules"). Each entry MUST
     include the migration path. Delete the section if there are none. -->

## Changelog

<!-- Paste the curated CHANGELOG.md section here (Added / Changed / Deprecated /
     Removed / Fixed / Security). -->

## Verification

- `make ci` — green on the release commit.
- `make coverage` — Python coverage ≥ 95 %, TS coverage ≥ 85 % lines / 75 % branches.
- `make build-all` — sdist + wheel + npm tarball + Docker runner image all produced.
- `make inspect-all` — no secrets, no `.git`, no `.env` in any built artifact.

## Signed off

- Owner: @ohswedd
- Pre-1.0 review: [`docs/release/pre-1.0-review.md`](docs/release/pre-1.0-review.md)

_No AI tools are co-authors of this release (CLAUDE.md §3)._
