---
title: Visual regression
description: Pillow-driven pixel + SSIM diff with hard CI-acceptance guard.
status: Stable
---

`sentinel visual` compares per-route screenshots against committed
baselines under `.sentinel/baselines/`. The diff math is pure-Python
Pillow: per-channel difference collapsed to a binary mask, plus
single-scale SSIM on the luminance channel.

.

## Three findings

| Category                 | Severity                               |
| ------------------------ | -------------------------------------- |
| `visual_pixel_diff`      | medium                                 |
| `visual_size_mismatch`   | high (pixel-dim drift is rarely noise) |
| `visual_missing_current` | medium                                 |

`missing_baseline` is the operator's signal to accept, not a finding.

## Three default viewports

```
mobile 375 × 812
tablet 768 × 1024
desktop 1280 × 800
```

Add more via `visual.viewports`. Name pattern `^[a-z0-9_-]+$`.

## Hard CI-acceptance guard

`sentinel visual accept` refuses to promote a baseline when:

- `state.ci` is true
- `CI` or `SENTINEL_CI` is truthy in the env

This is non-negotiable. The refusal writes a
`visual.accept.refused_ci` audit-log entry so operators have a paper
trail.

## CLI

```bash
uv run sentinel visual diff --url http://127.0.0.1:5001
uv run sentinel visual accept --viewport desktop --route /
uv run sentinel visual capture --url http://127.0.0.1:5001
```
