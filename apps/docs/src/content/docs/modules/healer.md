---
title: Healer / self-repair
description: Conservative repair proposals with banner-aware apply.
status: Stable
---

`sentinel fix` proposes deterministic repairs for failing tests:
locator updates, wait removals, fixture rebuilds. Apply is
banner-aware — the healer refuses to overwrite hand-edited files
unless `--allow-weaken` is set, and the assertion-weakening guard
rejects any proposal that decreases the assertion count.

.

## Three proposers

| Proposer                 | Confidence tiers                            |
| ------------------------ | ------------------------------------------- |
| `propose_locator_repair` | 0.5 / 0.7 / 0.75 / 0.9 / 0.95               |
| `propose_wait_repair`    | 0.3 / 0.6 / 0.9                             |
| `propose_fixture_repair` | 0.7 (contract drift), 0.85 (missing entity) |

## Auto-apply gating

Three modes: `off | safe | aggressive`. The
`decide_auto_apply` matrix considers:

- banner status (present + fresh)
- `requires_human_review` flag on the proposal
- confidence ≥ `--threshold`
- `--allow-weaken` (assertion-count safety)

Every applied repair logs the gating decision verbatim to `audit.log`.

## Always forbidden

- Weakening assertions to force green
- Changing test intent silently
- Hiding app bugs as test repairs
- Auto-accepting uncertain fixes
- Overwriting files without the banner

## CLI

```bash
uv run sentinel fix --latest --apply safe --threshold 0.9
```

Default is `--review-only` — proposals written to `<run-dir>/healer/`,
nothing applied.
