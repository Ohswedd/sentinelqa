---
title: Install
description: Install SentinelQA locally or in CI.
status: Stable
---

SentinelQA ships as a Python CLI (`sentinel`) plus a TypeScript runtime
(`@sentinelqa/ts-runtime`). Both are required for the full Playwright
audit loop; the CLI alone is enough for discovery, planning, and reporter
work against existing artifacts.

## Requirements

- Python 3.11 or 3.12
- Node.js 20 or 22
- pnpm 9.x
- (Optional) Docker for the isolated runner

## From a clone

```bash
git clone https://github.com/Ohswedd/sentinelqa.git
cd sentinelqa
make install
```

`make install` invokes `uv sync --frozen --all-packages` and
`pnpm install --frozen-lockfile`, plus `pre-commit install` if hooks
are configured.

## Verify

```bash
uv run sentinel --version
uv run sentinel doctor
```

`sentinel doctor` reports Python, Node, Playwright, config, and disk
checks. Anything red is a blocker; fix it before running an audit.

## Next steps

- [Quickstart](/get-started/quickstart/) — your first audit
- [Doctor reference](/get-started/doctor/) — what each check means
