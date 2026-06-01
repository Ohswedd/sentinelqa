# ADR-0026: Visual regression — Pillow-driven diff, signal-side capture, hard CI-acceptance guard

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

the documentation names the visual-regression module as a release-confidence
input: capture per-viewport PNGs of each in-scope route, diff against
committed baselines, surface findings the operator can review before
merging. our engineering rules: baselines never
auto-accept in CI, dynamic content must be maskable, and the report
must distinguish intentional change from likely regression with
evidence rather than guessing.

Three structural decisions framed the implementation:

1. **Where the diff math runs.** The task file (`03-diff-threshold.md`) floats both a TS-side `pixelmatch` pipeline and a Python-side Pillow pipeline. The TS path is faster on raw throughput but adds a second inter-runtime contract and forces every test to spin up Node, which the other modules do not require for their unit tier.
2. **Whether the module captures.** Capture means driving Playwright through the Phase-04 TS runtime to write PNGs into a known tree. Diff means consuming PNGs that already live on disk. The other already-shipped modules (`security`, `llm_audit`) consume signals that an earlier phase captured. Mirroring that pattern keeps the visual module testable without a browser.
3. **How baseline acceptance is gated.** the engineering guidelines-accept. The question is where the guard lives — inside the library (refuse `promote_to_baseline` when an env var is truthy) or at the CLI (refuse the `accept` subcommand). A library guard ties the policy to a global env-var read that's awkward to unit-test; a CLI guard keeps the policy at the system boundary and lets the library remain a pure-function surface.

## Decision

ships a Pillow-driven Python module under `modules/visual/`
that consumes PNGs already on disk. Concretely:

- **Facade.** `VisualModule(SentinelModule)` follows the lifecycle every other module follows (`validate_prerequisites` → `plan` → `execute` → `emit_findings` → `emit_metrics` → `summarize`). `plan` returns an empty spec set; the work is enumerated inside `execute` from the baseline and current-capture trees.

- **Diff math in Python (Pillow).** `modules/visual/diff.py` exposes `pixel_diff` (per-channel `ImageChops.difference` collapsed to a binary mask, plus a red-highlighted overlay PNG) and `ssim` (single-scale Wang et al. SSIM on the luminance channel, no Gaussian window so the value is platform-stable). The perceptual filter is a noise filter: findings fire only when the pixel threshold AND the SSIM threshold both cross.

- **Storage layout.** Baselines live at `.sentinel/baselines/<viewport>/<route-slug>.png` with an `index.json` carrying sha256, captured-at, captured-by-run-id, and the applied masks per row. Schema version `"1"` until a structural change justifies a bump.

- **Masking contract.** `visual.masks` accepts either a `selector` (the TS capture helper hides the element before screenshot) or a static `rect` (the Python diff layer paints both images grey before comparison). Selector-only masks are recorded but not drawn — the capture layer is responsible. The wildcard route `*` applies a mask to every captured route; the prefix glob `admin*` applies it to every route that begins with `admin`.

- **Viewport contract.** Defaults match the the documentation reference: `mobile (375×812)`, `tablet (768×1024)`, `desktop (1280×800)`. Viewport name is the on-disk segment, lowercased + alnum-only.

- **CI-acceptance guard at the CLI boundary.** `sentinel visual
accept` refuses to promote PNGs into the baseline tree whenever `state.ci` is true OR `CI` / `SENTINEL_CI` is truthy in the environment. The refusal writes an audit-log entry (`event:
"visual.accept.refused_ci"`) under the supplied current root so operators have a paper trail of every CI-blocked attempt. Exit code is `4` (unsafe target), matching the safety-boundary semantics the rest of the CLI uses.

- **Wire format.** The run's `visual/index.json` records every evaluated `(viewport, route)` pair with its status (`match` / `differ` / `missing_baseline` / `missing_current` / `size_mismatch`), the diff fraction, the differing-pixel count, the SSIM value (when perceptual is enabled), the threshold, and the baseline sha256 (for cross-run attribution). Diff overlays land under `visual/diff/<viewport>/<route-slug>.png`.

## Consequences

- **Positive.** Deterministic Python-only diff math means the entire unit tier runs in milliseconds without spinning Node; reviewers can reproduce findings locally with the same toolchain that produced them. The CLI-side CI guard keeps the safety boundary at the system edge and unit-testable. The selector + rect mask split lets test fixtures cover dynamic-content suppression without driving a real browser.

- **Negative / trade-off.** Pillow's pixel iteration is slower than pixelmatch on large captures (the documentation reference budget is acceptable, but we'll feel the difference when a future phase captures full-page 1920×4000 PNGs at p99). Path forward: revisit the TS-side option once the capture pipeline is mature enough to amortise the inter-runtime cost.

- **Follow-up obligations.** ships the diff + acceptance pipeline only. A future phase wires the Playwright TS runtime to populate `<run-dir>/visual/current/` and to honour selector-mask hide-before-screenshot. That capture layer is intentionally NOT a deliverable per the task files; it's the natural extension for the+ TS-runtime work and is tracked there.

## Alternatives considered

- **TS-side `pixelmatch` diff.** Faster per-pixel throughput but doubles the inter-runtime contract surface and forces every visual unit test to spin Node. Rejected because the current unit tier finishes in 0.3s and Pillow scales adequately for the the documentation's reference viewports.
- **Library-side CI guard via env-var read.** Awkward to unit-test (every test needs to monkeypatch the env), and the engineering guidelines's "no auto-accept in CI" is a CLI-level policy, not a data-layer invariant. Rejected in favour of the CLI guard.
- **Selector-only masking.** Simpler contract but unmaskable in unit tests without driving a browser. Rejected because the rect mask is required for fixture-driven coverage of the dynamic-content suppression behaviour.
- **Single shared baseline across viewports.** Rejected because responsive UIs render genuinely different content at mobile vs desktop; conflating them collapses the signal.

## References

- the documentation section(s): the documentation (Visual), our product spec (Risks — visual noise), the documentation (visual config block), the documentation (`sentinel visual`).
- our engineering rules rule(s): our engineering rules(Module contract), §13 (CLI rules), §29 (Visual regression rules), §39 (CI rules).
- External: Wang, Z. et al., "Image Quality Assessment: From Error Visibility to Structural Similarity," IEEE TIP 2004 (SSIM derivation).
- Related ADRs: ADR-0015 (module contract), ADR-0023 (MCP/agent interface — the `sentinel visual` CLI commands surface through the audit lifecycle the MCP server already drives).
