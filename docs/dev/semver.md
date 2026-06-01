# Semantic-versioning policy

Status: `Stable`

.md`§14 (SDK rules),`docs/dev/schema-versioning.md` (independent integer-major schema versions).

This page is the contract for how SentinelQA versions its published artefacts. It is read alongside `docs/dev/schema-versioning.md` (which governs the integer-major versions baked into every JSON artifact) and the SDK API snapshot at `packages/python-sdk/api-snapshot.json`. Skipping any rule here is a our engineering rules

## Scope

The policy below covers every artefact SentinelQA ships from this monorepo:

- Python distributions - `sentinelqa` (Python SDK; `packages/python-sdk/`) - `sentinelqa-cli` (Typer CLI; `apps/cli/`) - `sentinelqa-engine` (engine library; `engine/`) - `sentinelqa-mcp` (MCP server; `packages/mcp-server/`)
- npm distributions - `@sentinelqa/ts-runtime` (`packages/ts-runtime/`) - `@sentinelqa/shared-schema` (`packages/shared-schema/`) — private, internal-only today
- Docker image - `mcr.microsoft.com/playwright`-based runner built by `make build-runner-image` (ADR-0013)

All Python distributions are licensed Apache-2.0. The TS distributions follow the root `LICENSE`.

## Pre-1.0 rules

Until the first **1.0.0** tag is published, the project is pre-1.0 and the following apply:

1. **Breaking changes are allowed in minor versions.** A breaking change is anything that would break a downstream consumer who has pinned the previous minor — removed CLI flag, renamed SDK symbol, changed exit-code mapping, removed config key, removed report field, etc.
2. **Every breaking change must be documented.** A breaking change requires: - A `### Removed` or `### Changed` entry in `CHANGELOG.md` at the version that introduces it. - If it affects an architectural decision listed in our engineering rules - If it affects a documented the documentation contract (CLI in §13, SDK in §14, MCP in §16, reports in §20, lifecycle in §10, …), an explicit the documentation edit in the same branch. - For the Python SDK specifically: a refreshed `packages/python-sdk/api-snapshot.json` and a one-line entry in `packages/python-sdk/__deprecation_policy.md`.
3. **No silent breaks.** A breaking change that ships without all of the above is a regression, not a release. The pre-1.0 review blocks any tag that fails this check.
4. **Patch versions are always backwards-compatible.** A `0.X.Y → 0.X.(Y+1)` bump must not break anything documented.
5. **Version numbers move forward only.** No re-cutting a tag. A bad release is yanked and a new patch is cut.

After the first **1.0.0** tag, classic SemVer applies: breaking changes require a major bump, additive changes a minor, fixes a patch. Promotion criteria for 1.0.0 are listed in and the pre-1.0 review.

## Schema versions are independent

Every machine-readable artefact SentinelQA emits (`run.json`, `findings.json`, `score.json`, `RootConfig`, `RepairSuggestion`, the agent-message envelope, the plugin manifest, etc.) carries its own integer-major schema version. Those versions are governed by `docs/dev/schema-versioning.md` and live in `engine/domain/schema.py`.

The package version (the value in `pyproject.toml` / `package.json`) and the schema version do **not** track each other:

- Bumping `sentinelqa` from `0.1.0` to `0.2.0` does NOT imply a schema bump.
- Bumping `RUN_SCHEMA_VERSION` from `"1"` to `"2"` IS itself a breaking change, so it MUST coincide with at least a minor package version bump and a `### Changed` changelog entry.

Consumers that only read the schemas (e.g. external dashboards) pin against the schema version, not the package version.

## SDK public surface is frozen via snapshot

`packages/python-sdk/api-snapshot.json` is the source-of-truth for the `sentinelqa` public surface. The unit test `tests/unit/sdk/test_api_snapshot.py` diffs a freshly-dumped surface against the committed snapshot on every CI run.

Rules:

- Any change to the public surface — adding a symbol, removing a symbol, changing a signature, changing a type, changing a `Final` constant value — requires the snapshot to be regenerated in the same branch (`make sdk-api-snapshot`).
- **Removing** a public symbol or changing an existing signature is a breaking change and follows the pre-1.0 rules above (ADR + `### Removed`/`### Changed` changelog entry + our product spec edit when relevant).
- Adding a new public symbol is additive and only needs a `### Added` changelog entry.

`packages/python-sdk/__deprecation_policy.md` documents the deprecation window contract: a symbol marked `Deprecated` stays in place for at least one minor version after the deprecation lands, with an emitted `DeprecationWarning` and a `### Deprecated` changelog entry. The actual removal lands in the next minor and is recorded under `### Removed`.

## Tag plan

The release calendar is driven by the engineering milestones in our product spec and the recommended build order in our product spec Each tag is a real artifact produced by `make build-all` and inspected by `make inspect-all`. No tag is published without a sign-off line in the pre-tag review process.

| Tag      | When                         | Captures                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| -------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `v0.1.0` | After (CI Integration)       | release: domain models + CLI + lifecycle + reporter pipeline + TS runtime + discovery + planner + generator + runner + analyzer + functional / accessibility / performance / security / quality scoring / HTML+JSON reports / SDK / CI integration. our product spec release.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `v0.2.0` | After (LLM-code audit)       | Adds MCP & Agent Interface and the LLM-code audit module — the public differentiator (the documentation, §28).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `v0.3.0` | After (Visual Regression)    | Adds the Healer / Self-Repair and the visual-regression module.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `v0.4.0` | After (Chaos Module)         | Adds API testing and the chaos / adversarial module.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `v0.5.0` | After (Integrations)         | Adds the Plugin Architecture and the Integrations adapter set.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `v0.6.0` | After (Docs & ADRs)          | Adds the example apps and the docs site + ten new ADRs.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `v0.7.0` | After (release-engineering)  | Captures the surface — semver policy, changelog, package metadata, distribution scripts, trademark verdict, pre-1.0 review checklist. Versions bumped to `0.7.0` across all 6 publishable Python pyprojects + `packages/ts-runtime/package.json`. **No publication.** Owner-only registered-marks rows in the pre-tag review process must clear before the tag lands.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `v1.0.0` | After (Publish to Ecosystem) | First publication-eligible tag. Captures – 36 end-to-end — multi-provider LLM adapters (, ADR-0042), browser-authenticated audits (, ADR-0043), extended security skill catalog with `FINDINGS_SCHEMA_VERSION` bump 1→2 (, ADR-0044), supply-chain & dependency audit (, ADR-0045), compliance packs (, ADR-0046), public release engineering (, ADR-0047), and the publish workflows + dry-runs + post-publish smoke + owner runbook themselves (, ADR-0048). Versions bumped to `1.0.0` across all six publishable Python pyprojects + `packages/ts-runtime/package.json` (and the `private:true` flag dropped on the TS package; `files:` whitelist tightened to `dist/` + `LICENSE` + `README.md`; `publishConfig.access: public` + `publishConfig.provenance: true`). The Docker runner image is tagged `sentinelqa/runner:1.0.0`. Requires explicit human-owner go-ahead per our engineering rules+ the trademark rows + signature in the pre-tag review process. |

Each tag corresponds to a single squash-merge commit on `main` plus a paired `git tag -s vX.Y.Z` and a release entry in `CHANGELOG.md`. The first six tags above are retrospective — they record what `main` looked like at each merge — and are filed only after the trademark verdict is recorded and the pre-1.0 review is signed.

** itself produces no tag.** The phase ships the release-engineering surface; the actual tagging is gated on a human-owner go-ahead.

## Version source-of-truth

Each Python distribution carries its own `version` field in its `pyproject.toml`. The matching `[project.version]` table in `apps/cli/pyproject.toml` is the canonical version for the `sentinel --version` command (`engine.version`-driven; reads `importlib.metadata`).

For npm distributions, the `version` field in each `packages/*/package.json` is the source-of-truth.

The Docker runner image is tagged with the `sentinelqa-cli` version (e.g. `sentinelqa-runner:0.7.0`).

A future single-source bump tool may be added in, but the contract today is "every manifest carries its own version, and the pre-1.0 review checks that they all match at tag time".

## Yanking a release

If a published tag turns out to be broken — wrong contents, security regression, accidental publication — the procedure is:

1. Cut a new patch with the fix. Add a `### Fixed` entry that names the bad version.
2. On PyPI / npm: mark the bad version yanked. Do NOT delete it; yanking preserves history.
3. Document the yank in `CHANGELOG.md` under the new patch's `### Removed` block.

Force-pushing or rewriting a tag is forbidden by our engineering rules(privacy/ownership) and the standing authorization rules.
