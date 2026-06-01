# ADR-0035: Generated tests live in the user's repo

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #2 asked whether generated Playwright tests
should live in the user's repository or under `.sentinel/generated/`.
The PRD's recommended answer was "in the user repo with clear
generated-file markers," and the generator (ADR-0012) shipped
specs to `tests/sentinel/` with a mandatory banner.

This ADR is one of the eight Phase-27 open-question ADRs.

## Decision

**Generated specs live under `tests/sentinel/` in the user's
repository, each file beginning with a banner that names the
generator and records the generation timestamp.** Page objects and
fixtures live under `tests/sentinel/page-objects/` and
`tests/sentinel/fixtures/`. The healer + generator detect the banner
and refuse to overwrite hand-edited files unless `--force` /
`--allow-weaken` is supplied (ADR-0012, ADR-0025).

`.sentinel/runs/<id>/` is reserved exclusively for **run artifacts**
(run.json, findings.json, score.json, traces, logs, audit log). The
generator never writes to `.sentinel/`.

## Consequences

- **Positive:** generated specs are version-controlled alongside the app code. Users can read them, diff them, regress against them, and hand-edit them where the heuristics fall short.
- **Positive:** CI integrators don't need a special "restore generated tests" step — the specs are checked in like any other source file.
- **Positive:** the banner-aware overwrite policy makes the healer safe-by-default; hand edits survive regeneration.
- **Negative / trade-off:** users who only want SentinelQA for CI smoke have to either gitignore `tests/sentinel/` or commit machine-generated code. Documented in the quickstart.
- **Negative / trade-off:** the user repo's test inventory grows over time; the generator's diff-vs-prior summary keeps the noise visible.
- **Follow-up obligations:** keep the banner-detection regex authoritative and tested (`tests/unit/healer/test_banner.py`); never add a code path that writes generated specs to `.sentinel/`.

## Alternatives considered

- **Write generated specs to `.sentinel/generated/`.** Rejected — hides the generated code from review tooling, complicates the user's `playwright.config.ts`, and breaks the banner-aware hand-edit safety story.
- **Per-run regeneration with no on-disk artifact.** Rejected — defeats the healer (no file to repair), defeats CI caching, and removes the user's ability to review what's being run.

## References

- our product spec Open Question #2 + recommended answer
- the documentation Generator module
- our engineering rules-healing rules (banner safety)
- Related ADRs: ADR-0012 (Generated test conventions), ADR-0025 (Healer)
