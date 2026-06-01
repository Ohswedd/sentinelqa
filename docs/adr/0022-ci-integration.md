# ADR-0022: CI integration — modes, diff-aware selection, posters, Action

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

lights up the CI integration surface (our product spec, our engineering rules):

- A `sentinel ci` command with five preset modes — `fast`, `standard`, `full`, `nightly`, `release` — that cover the the documentation contract.
- A diff-aware test selector that turns a git diff range into impacted routes / endpoints / test files (the documentation, §12.3).
- A drop-in GitHub composite Action and reusable workflow.
- A drop-in GitLab template.
- Upsert posters that surface the run summary on PR / MR review.
- A SARIF upload step that publishes findings to GitHub code scanning.

The challenge is keeping the lifecycle (`engine.orchestrator`) unaware
of CI specifics — modes are presets, not new code paths — while still
making the CI surface predictable for a contributor copy-pasting a
workflow into their project.

## Decision

We introduce `engine/ci/` as the integration layer:

- `engine.ci.modes.apply_mode(config, mode, fail_under=None)` returns a `(RootConfig, ModePlan)` pair. Each mode is a recipe over three knobs: `modules` (which audit modules to run), `grep` (Playwright tag filter threaded through `module_options["functional"]["grep"]`), and `policy_overrides` (the `release` mode raises `policy.min_quality_score` to `max(config, 90)`). Module presets always intersect with the user's enabled module set so the config remains authoritative for the safety boundary.
- `engine.ci.diff_aware.select_from_files(diff_range, changed_files)` is a pure helper that walks the file list with deterministic framework-shape heuristics (Next.js App Router, Next.js Pages Router, Vite). A broad-impact tripwire — lockfiles, framework configs, Dockerfile — forces fallback to full mode. A volume tripwire (`> 50` changed files) does the same. The smoke tag (`@p0`) is the floor — every diff still runs smoke.
- The `sentinel ci` CLI command translates these into the existing `RunLifecycle.execute` inputs (`requested_modules`, `module_options`); the lifecycle itself is unchanged. A new `<run-dir>/ci.json` sidecar persists the mode, the diff range, and the resolved selection so the PR comment / HTML report can show what ran.
- The GitHub composite action (`integrations/github/action.yml`) and reusable workflow (`integrations/github/workflows/sentinel-pr.yml`) exist in-repo so projects can either `uses:./integrations/github` (for development branches) or pin a version tag (post release). The Action's output reads `quality-score` / `release-decision` / `report-html-url` from the latest `score.json`.
- PR / MR posters use `urllib` (no `requests` dep), honor a `<!-- sentinelqa:pr-comment -->` upsert anchor ( contract), and read tokens from env vars only. Retries: 3 attempts with exponential backoff on `429` / `5xx`; `Retry-After` headers honored.
- The `sentinel ci` command always forces `--ci=True` so JSON output is deterministic regardless of how it's invoked.

## Consequences

- **Positive:** - Modes stay declarative — adding a sixth mode is a one-recipe change in `engine.ci.modes`, no lifecycle edits. - Diff-aware selection is pure: the same file list deterministically produces the same selection, which is testable without any git setup. - GitHub and GitLab posters share an anchor with the `engine.reporter.pr_comment` writer, so the entire poster flow can upsert without parsing rendered Markdown. - The composite Action and template are testable structurally — a YAML-load + assertions test guarantees the documentation conformance.
- **Negative / trade-off:** - The diff-aware heuristics are framework-shape-aware (Next.js, Vite); less-common layouts fall back to full mode. We accept this — the tripwire defaults to safety over precision, and adding new shapes is a future plug-in opportunity rather than a fragile guess. - The `_RELEASE_MIN_QUALITY_SCORE = 90` constant lives in `engine.ci.modes` rather than the config schema. Projects that want a different release floor should pass `--fail-under` explicitly; that override is authoritative.
- **Follow-up obligations:** - When ships API testing, the diff-aware OpenAPI tag (`@module:api`) should start a real selection chain through the new API module's tag set rather than relying on the full-module-run fallback.

## Alternatives considered

- **Make modes mutate `ModulesConfig` directly.** Rejected because config mutation hides what a CI mode does — a contributor inspecting `config.snapshot.yaml` would see modules disabled even when the user's `sentinel.config.yaml` had them on, leading to mistaken assumptions about default behavior. Threading the request through `RunLifecycle.execute(requested_modules=...)` keeps the config pristine.
- **Treat diff-aware selection as an LLM step.** Rejected because the selection must be deterministic and reproducible across runs. Static file-path heuristics meet the bar; LLMs make this slower, more expensive, and harder to test.
- **Ship one composite Action per mode.** Rejected as YAML duplication; `mode` becomes an input instead.
- **Use the `requests` library for the PR posters.** Rejected per our engineering rules— `urllib` is sufficient for a thin HTTP client and carries no dep risk.

## References

- PRD section(s): the documentation (Regression suite), §12.3 (PR diff audit), §13 (CLI), §21 (CI/CD).
- our engineering rules rule(s): our engineering rules(Safety boundary), §10 (Run lifecycle), §13 (CLI rules), §17 (Quality gates), §33 (Logging and secrets), §35 (Dependency rules), §39 (CI rules).
- Related ADRs: [ADR-0007](./0007-run-lifecycle.md) (Run lifecycle), [ADR-0010](./0010-discovery-mvp-http-first.md) (HTTP-first discovery, Playwright backend follow-up resolved in this phase), [ADR-0015](./0015-module-contract-and-functional-module.md) (Module contract — modes thread `--grep` into the functional module via `module_options`).
