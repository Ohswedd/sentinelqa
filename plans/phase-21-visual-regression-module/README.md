# Phase 21 — Visual Regression Module

## Objective

Implement visual baselines, diff thresholds, dynamic-content masking, and per-breakpoint snapshots (PRD §10.6 / §29 / CLAUDE §29). Baselines never auto-accept in CI.

## PRD / CLAUDE.md references

- PRD §10.6 Visual, §29 Risks (visual noise), §31 open question 7.
- CLAUDE.md §29 Visual regression rules.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `VisualModule`.
2. `02-baseline-storage.md` — `.sentinel/baselines/` layout.
3. `03-diff-threshold.md` — Pixel/percentage threshold + perceptual diff option.
4. `04-masking.md` — Mask dynamic regions (clocks, ads, animated banners).
5. `05-breakpoints.md` — Multiple viewport snapshots.
6. `06-no-ci-auto-accept.md` — Hard guard against accepting baselines in CI.
7. `07-visual-cli.md` — `sentinel visual` command.
8. `08-tests.md` — sweep.

## Definition of Done

- Baseline workflow documented; first-run captures, second-run diffs.
- CI never auto-accepts.
- Findings include before/after images + diff overlay.

## Phase Gate Review

- [ ] Baseline workflow tested.
- [ ] CI auto-accept blocked by hard guard.
- [ ] Masking works on dynamic fixture.
- [ ] `STATUS.md` updated.
