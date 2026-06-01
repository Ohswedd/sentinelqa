# ADR-0040: Built-in visual diff engine first, integrations later

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #7 asked whether SentinelQA should provide its
own visual-diff engine or integrate with existing providers. The
recommended answer was "basic built-in visual diff first, integrations
later." Phase 21 (ADR-0026) shipped a pure-Python visual module:
Pillow-driven pixel diff plus single-scale SSIM on the luminance
channel, with a hard CI-acceptance guard.

This ADR is one of the eight Phase-27 open-question ADRs.

## Decision

**SentinelQA owns the visual-diff engine in the MVP.** Hosted visual
services (Percy, Chromatic, Applitools) are not integrated yet — they
fall into the cloud-boundary deferral (ADR-0033) and can ship as
out-of-tree `ScannerPlugin` integrations post-MVP.

The built-in engine:

- Uses Pillow for image I/O + diff masks.
- Uses single-scale luminance SSIM (no Gaussian window — platform- stable).
- A finding fires only when **both** the pixel threshold AND the SSIM threshold cross (perceptual filter is noise reduction only).
- Stores baselines under `.sentinel/baselines/<viewport>/<route-slug>.png` with an atomic `index.json` ledger.
- Hard-refuses CI acceptance: `sentinel visual accept` exits 4 if `state.ci` is true or `CI` / `SENTINEL_CI` is truthy in env.

## Consequences

- **Positive:** zero third-party dependency for visual checks. Pillow is a small, stable, well-trusted Python image library.
- **Positive:** consistent with the local-first / no-cloud posture — baselines live next to the user's code.
- **Positive:** the hard CI-acceptance guard prevents the most common visual-regression footgun (auto-accepting a regression on green).
- **Negative / trade-off:** the built-in engine is simpler than multi-scale SSIM or perceptual hash-based services. Acceptable — the documented contract is "noise filter on top of pixel diff," not "the world's best perceptual diff."
- **Negative / trade-off:** cross-team baseline sharing is a manual ops problem. Users who need it commit baselines to git or use an external artifact store.
- **Follow-up obligations:** if a Percy / Chromatic / Applitools integration ever lands, it ships as an out-of-tree plugin and this ADR is updated (not superseded) with a "see also" pointer.

## Alternatives considered

- **Integrate with Percy / Chromatic / Applitools first.** Rejected — adds a hosted dependency to the MVP, conflicts with ADR-0033, and forces every user into someone else's pricing.
- **No visual module in the MVP.** Rejected — visual regression is part of the documentation scope and a real differentiator for the release-confidence story.

## References

- our product spec Open Question #7 + recommended answer
- the documentation Visual regression
- our engineering rules
- Related ADRs: ADR-0026 (Visual regression), ADR-0033 (Cloud boundary)
