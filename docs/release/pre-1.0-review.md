# Pre-1.0 release review

Status: `Stable`

Authority: `CLAUDE.md` §40 (Versioning & release rules), `docs/dev/semver.md` (pre-1.0 rules), `plans/phase-28-versioning-release/06-pre-1.0-review.md`.

This is the go/no-go checklist the human owner signs **before any pre-1.0 tag** lands on `origin/main`. Phase 28 ships the release surface (semver policy, changelog, package metadata audit, build + inspect scripts, trademark verdict); this doc is the gate that ratifies an actual tag.

## Sign-off contract

A tag is publishable when **every** row below is checked and the sign-off line at the bottom carries the owner's name + date + tag.

Phase 28 itself produces **no tag**. The first tag this checklist can ratify is `v0.7.0` (Phase 28 surface), per the tag plan in `docs/dev/semver.md`. Earlier tag rows (`v0.1.0`..`v0.6.0`) are retrospective and may be ratified later in a single sign-off block once the registered-marks lanes clear.

## Pre-tag checklist

Each item references the CLAUDE.md §40 bullet it satisfies.

### Engineering gates (CLAUDE.md §40 — "Tests pass")

- [ ] `make ci` is green on the tag commit. Paste the local summary line (Python + skipped + TS) under the sign-off.
- [ ] `make coverage` reports Python coverage ≥ 95 % on the tag commit. Paste the total under the sign-off.
- [ ] Vitest TS coverage ≥ 85 % lines / 75 % branches on the tag commit. Paste the totals under the sign-off.
- [ ] `make test-full` is green on the tag commit (includes the slow-tier build + install smoke test from `tests/integration/release/test_built_packages.py`).
- [ ] `make audit-metadata` is green on the tag commit (every publishable manifest carries release-ready metadata).

### Changelog (CLAUDE.md §40 — "Changelog updated")

- [ ] `CHANGELOG.md` contains a section for the tag with a real ISO date (no `Unreleased` left at the top of the tag's section).
- [ ] Every breaking change since the previous tag is recorded under `### Changed` or `### Removed` with a migration path (`docs/dev/semver.md` Pre-1.0 rule §2).
- [ ] If the Python SDK public surface changed: `packages/python-sdk/api-snapshot.json` is regenerated AND `tests/unit/sdk/test_api_snapshot.py` passes; `packages/python-sdk/__deprecation_policy.md` has a one-line entry per removed / changed symbol.
- [ ] Run `make changelog-draft VERSION=<tag> DATE=<YYYY-MM-DD>` and diff against `CHANGELOG.md`'s top section — every commit since the last tag is either in the curated section or intentionally omitted (chore/ci/docs are typically omitted).

### Version bumped (CLAUDE.md §40 — "Version bumped")

- [ ] `apps/cli/pyproject.toml`'s `project.version` matches the tag (or the next published version per `docs/dev/semver.md`).
- [ ] `packages/python-sdk/pyproject.toml`'s `project.version` matches the tag.
- [ ] `engine/pyproject.toml`'s `project.version` matches the tag.
- [ ] `modules/pyproject.toml` and `integrations/pyproject.toml` versions match the tag (or are pinned by `sentinelqa-cli`'s dependency spec).
- [ ] `packages/mcp-server/pyproject.toml`'s `project.version` matches the tag.
- [ ] `packages/ts-runtime/package.json`'s `version` matches the tag.
- [ ] The Docker runner image (`apps/cli/sentinel/runner/docker/Dockerfile.runner`) builds and tags with the same version (`make build-runner-image RUNNER_IMAGE=sentinelqa/runner:<tag>`).

### Docs updated (CLAUDE.md §40 — "Docs updated")

- [ ] `PRD.md` reflects the behavior shipped under the tag (CLAUDE.md §5).
- [ ] Every ADR triggered since the previous tag is `Accepted` (`scripts/check-adrs.sh`).
- [ ] `apps/docs/` Astro Starlight site builds clean (`make docs-build`) and the freshness gate passes (`make docs-check-fresh`).
- [ ] `docs/dev/semver.md` tag plan row for this tag reflects what actually ships.

### Security boundary reviewed (CLAUDE.md §40 — "Security boundary reviewed")

- [ ] CLAUDE.md §6 forbidden-feature deny-list: `tests/security/test_no_stealth_flags.py` is green on the tag commit. Same for module-specific security guards (`test_chaos_no_evasion_flags.py`, `test_api_no_aggressive_flags.py`, `test_mcp_safety.py`, `test_module_calls_policy.py`, `test_security_forbidden_flags.py`, `test_no_wcag_compliance_claims.py`, `test_synthetic_perf_labeling.py`).
- [ ] CLAUDE.md §33 redaction guard: `tests/property/test_redaction_property.py` is green on the tag commit (slow tier).
- [ ] CLAUDE.md §3 ownership: `git log --grep "Co-authored-by" v<prev>..HEAD` returns no AI co-author trailers; `make audit-metadata`'s AI-author guard is green.
- [ ] Integrations credential-leak guard: `tests/integration/integrations/test_credential_leak_guard.py` is green on the tag commit.

### Package contents inspected (CLAUDE.md §40 — "Package contents inspected")

- [ ] `make build-all` on the tag commit produces 6 Python wheels + 6 Python sdists + 1 TS tarball.
- [ ] `make inspect-all` reports `ok` for every artifact (no `.git`, no `.env`, no PEM/SSH keys, no cloud-credential files, no `__pycache__`, no `*.pyc`).
- [ ] Install one of the built wheels into a fresh venv and run `sentinel --version` — exit 0, version matches the tag. Covered by the slow-tier `tests/integration/release/test_built_packages.py::test_build_inspect_install_and_run_sentinel_version`.
- [ ] If publishing the Docker runner image: build it (`make build-runner-image RUNNER_IMAGE=sentinelqa/runner:<tag>`) and inspect it for forbidden contents.

### Trademarks (additional to CLAUDE.md §40, from `plans/phase-28-versioning-release/05-trademark-check.md`)

The Phase 28 verdict at `docs/dev/trademarks-and-naming.md` clears the common-law lanes (PyPI / npm / GitHub / general web). The registered-marks lanes remain owner-only and are explicit pre-tag blockers for any tag that exercises public publication:

- [ ] **USPTO TM search** at <https://tmsearch.uspto.gov/> completed by the human owner; verdict + date + screenshot URL recorded in `docs/dev/trademarks-and-naming.md`.
- [ ] **EUIPO TMview** at <https://www.tmview.tmdn.org/> completed by the human owner; verdict recorded.
- [ ] **UKIPO mark search** at <https://www.gov.uk/search-for-trademark> completed by the human owner; verdict recorded.
- [ ] If any verdict is _conflict_: stop the tag, propose alternatives in `docs/dev/trademarks-and-naming.md`, write the re-clearance ADR per that doc's "What changes the verdict" section, and only resume after the ADR is `Accepted`.

These three rows do **not** block tags that are NOT being published (the retrospective `v0.1.0`..`v0.6.0` rows below); they DO block `v0.7.0+` whenever an actual `pnpm publish` / `twine upload` / `docker push` would follow.

### Distribution surface (not in CLAUDE.md §40 but required by `plans/phase-28-versioning-release/`)

- [ ] `docs/dev/semver.md` is current — no row needs updating to reflect what this tag actually captures.
- [ ] The pre-1.0 review **for this tag** is signed off (sign-off block below).
- [ ] No publication is performed without an explicit "go ahead" message from the owner — `CLAUDE.md` §40 ("Do not publish packages without explicit approval"). The act of signing this file is permission to **tag**, not to **publish**.

## Sign-off

Each tag gets one sign-off block here. Append; do not edit prior blocks.

### Template

```
## Tag: v<MAJOR>.<MINOR>.<PATCH>
Date:           <YYYY-MM-DD>
Owner:          <human-owner-name>
Commit:         <full-sha>
Branch:         <branch-name>

make ci:        <pytest summary> | TS: <vitest summary>
make coverage:  Python <pct>% (floor 95%) | TS <lines%>/<branches%> (floors 85/75)
make test-full: <added slow-tier summary>
make build-all: 6 wheels + 6 sdists + 1 TS tarball ok
make inspect-all: ok — N artifact(s) inspected, no forbidden files

Trademark clearance:
  - USPTO:   <status + date + screenshot URL>
  - EUIPO:   <status + date + screenshot URL>
  - UKIPO:   <status + date + screenshot URL>

Publication intent: <none | PyPI | npm | Docker | combination>
Notes:          <anything noteworthy>

Signed: <owner-name>
```

### Active sign-offs

_None signed yet — the first tag (v0.7.0) requires the registered-marks rows above to clear before this block is signed and applied as a tag._

### Draft sign-off — v1.0.0 (prepared 2026-06-01, awaiting owner)

Phase 36 (Publish to Ecosystem) closed on `feature/phase-36-publish-ecosystem`. All engineering, build, inspection, audit, and changelog gates below were re-verified on the close-out commit. The four owner-only rows (USPTO / EUIPO / UKIPO / signature) are intentionally blank — they remain pre-tag blockers for the actual `git tag -s v1.0.0` (`CLAUDE.md` §40 + `docs/dev/semver.md` pre-1.0 rule §5).

```
## Tag: v1.0.0
Date:           2026-06-01
Owner:          <human-owner-name>     ← owner to fill in
Commit:         <to be set at merge time of feature/phase-36-publish-ecosystem>
Branch:         feature/phase-36-publish-ecosystem

make ci:        <pytest summary on tag commit> | TS: <vitest summary on tag commit>
make coverage:  Python <pct>% (floor 95%) | TS <lines%>/<branches%> (floors 85/75)
make test-full: <added slow-tier summary on tag commit>
make audit-metadata: ok — 16 manifests audited
make audit-license-headers: ok — SPDX coverage + foreign-SPDX drift clean
make build-all: 6 Python wheels + 6 Python sdists + 1 TS tarball (sentinelqa-ts-runtime-1.0.0.tgz); 13 artifacts total
make inspect-all: ok — 13 artifact(s) inspected, no forbidden files

Trademark clearance:
  - USPTO:   <verdict + date + screenshot URL>   ← owner to complete
  - EUIPO:   <verdict + date + screenshot URL>   ← owner to complete
  - UKIPO:   <verdict + date + screenshot URL>   ← owner to complete

Publication intent: PyPI + npm + Docker Hub + GitHub Release (the v1.0.0 row in `docs/dev/semver.md` is publication-eligible; the publish-runbook at `docs/release/publish-runbook.md` is the owner-driven execution path)
Notes:          v1.0.0 covers Phases 30 – 36 (multi-provider LLM, browser-authenticated audits, extended security catalog with `FINDINGS_SCHEMA_VERSION` 1→2, supply-chain audit, compliance packs, public-release engineering, ecosystem publish). All six publishable Python pyprojects and `packages/ts-runtime/package.json` are at `1.0.0`; the TS package drops `private:true`, tightens `files:` to `dist/` + `LICENSE` + `README.md`, and gains `publishConfig.access: public` + `publishConfig.provenance: true`. `CHANGELOG.md` has a curated `[1.0.0]` section. `docs/dev/semver.md` `v1.0.0` row updated. ADR-0048 (publish pipeline) accepted.

Signed: <owner-name>                  ← owner to sign
```

The act of filling in the four blank rows and the signature is permission to **tag**. Even after the tag, publication is gated by `docs/release/publish-runbook.md` — the agent never runs `twine upload` / `pnpm publish` / `docker push` / `git tag`; those are owner commands.

### Draft sign-off — v0.7.0 (prepared 2026-05-31, awaiting owner)

The engineering, build, inspection, audit, and changelog gates below were re-verified on the release-prep branch `feature/release-0.7.0`. The four owner-only rows (USPTO / EUIPO / UKIPO / signature) are intentionally blank.

```
## Tag: v0.7.0
Date:           2026-05-31
Owner:          <human-owner-name>     ← owner to fill in
Commit:         <to be set at merge time of feature/release-0.7.0>
Branch:         feature/release-0.7.0

make ci:        3027 Python tests passed + 2 skipped (Chromium-gated lanes) + 27 deselected | TS: 261 passed (31 test files)
make coverage:  Python 95.13% (floor 95%) | TS 88.14% lines / 78.26% branches (floors 85/75)
make test-full: 3054 Python tests passed + 2 skipped (incl. slow-tier build/install smoke; 9 hypothesis property tests; 15 tsc-acceptance tests)
make audit-metadata: ok — 16 manifests audited
make build-all: 6 Python wheels + 6 Python sdists + 1 TS tarball (sentinelqa-ts-runtime-0.7.0.tgz); 13 artifacts total
make inspect-all: ok — 13 artifact(s) inspected, no forbidden files

Trademark clearance:
  - USPTO:   <verdict + date + screenshot URL>   ← owner to complete
  - EUIPO:   <verdict + date + screenshot URL>   ← owner to complete
  - UKIPO:   <verdict + date + screenshot URL>   ← owner to complete

Publication intent: none (Phase 28's `v0.7.0` row in `docs/dev/semver.md` says "No publication"; the tag captures the release-engineering surface only)
Notes:          v0.7.0 covers Phases 28 (release-engineering) and 29 (final hardening & PRD reconciliation). All six publishable Python pyprojects and `packages/ts-runtime/package.json` are at `0.7.0`. `CHANGELOG.md` has a curated `[0.7.0]` section. `tests/integration/cli/test_subprocess_smoke.py::test_sentinel_version` now reads the version from `apps/cli/pyproject.toml` instead of pinning the literal, so future bumps don't drift. `tests/integration/generator/test_tsc_accepts_output.py` had a latent slow-tier breakage on `@types/node` resolution — fixed by pointing `typeRoots` at the workspace's `node_modules/@types`. Coverage and TS-coverage numbers are unchanged from Phase 29's gate row. No new ADRs.

Signed: <owner-name>                  ← owner to sign
```

The act of filling in the four blank rows and the signature is permission to **tag**. It is NOT permission to publish; CLAUDE.md §40 requires a separate explicit go-ahead before any `pnpm publish` / `twine upload` / `docker push`.
