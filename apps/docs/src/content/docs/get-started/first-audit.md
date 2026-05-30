---
title: Run your first audit (5 minutes)
description: Targeted walkthrough that takes a fresh user from clone to a green audit in under five minutes.
status: Stable
---

PRD §30.1 tracks this metric: a new user must be able to install
SentinelQA and produce a passing audit against the Next.js example in
under five minutes. This page is the script.

## Timer

| Step                                     | Wall-clock |
| ---------------------------------------- | ---------- |
| `make install`                           | ~90 s      |
| `make demo-nextjs` (cold)                | ~45 s      |
| `uv run sentinel audit` against the demo | ~2 min     |
| `uv run sentinel report --latest --open` | ~5 s       |

Total: under five minutes on a warm developer laptop. Cold first-time
runs pay the Playwright install cost (~1 min).

## Script

```bash
# 1. Clone + install
git clone https://github.com/Ohswedd/sentinelqa.git
cd sentinelqa
make install

# 2. Boot the Next.js example
make demo-nextjs       # serves at http://127.0.0.1:3000

# 3. Audit it
cd examples/nextjs
uv run sentinel audit

# 4. View the HTML report
uv run sentinel report --latest --format html --open
```

You should see:

- Discovery: routes, forms, an API surface, and the `/admin` boundary.
- Planner: ~12 flows (login / signup / CRUD / role / smoke).
- Generator: Playwright specs under `tests/sentinel/`.
- Runner: all tests pass against the demo.
- Score: ≥ 80 (the demo's configured floor).
- Release decision: `pass` or `pass_with_warnings`.

## When it goes wrong

If the audit comes back `blocked`:

- Open the HTML report — the **Critical blockers** card is pinned at
  the top.
- Each finding has a `Recommendation` and an `Evidence` link.
- See [Error codes](/errors/) if the CLI exited non-zero.

## What to try next

- [LLM-broken demo](/modules/llm-audit/) — the intentionally broken
  app that exercises ≥ 8 PRD §10.9 anti-patterns.
- [CI/CD setup](/cicd/) — wire SentinelQA into pull requests.
- [Python SDK](/sdk/) — call the engine programmatically.
