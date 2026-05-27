# Task 21.03 — Diff threshold

## Deliverables

- Diff using `pixelmatch` (TS) or `pillow`-based diff (Python); choose TS-side for speed.
- `visual.threshold` (0.0–1.0, % of differing pixels).
- Optional perceptual diff via SSIM (`structural_similarity_index`) for content where pixel-perfect is impractical.
- Findings include diff PNG, baseline, current, and the pixel-diff percentage.

## Acceptance criteria

- Fixture page with a deliberate one-letter change exceeds threshold; pristine match does not.

## Tests required

- `tests/integration/modules/visual/test_diff.py`.

## PRD / CLAUDE.md references

- PRD §10.6.
- CLAUDE.md §29.

## Definition of Done

- [ ] Diff + threshold + finding.
- [ ] `STATUS.md` updated.
