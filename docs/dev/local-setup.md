# Local development setup

Status: `Stable`

## Prerequisites

| Tool                               | Version                         | Why                                                                          |
| ---------------------------------- | ------------------------------- | ---------------------------------------------------------------------------- |
| Python                             | 3.11 or 3.12 (3.12 recommended) | Engine, SDK, CLI, modules, tests (the documentation, ADR-0002).              |
| Node.js                            | 20 LTS or 22                    | TypeScript runtime, ESLint, Vitest, Playwright (our product spec, ADR-0002). |
| [`uv`](https://docs.astral.sh/uv/) | 0.5.x                           | Python deps + lockfile + workspace (ADR-0003).                               |
| [`pnpm`](https://pnpm.io/)         | ≥ 9                             | TypeScript deps + workspace (ADR-0003).                                      |
| `make`                             | GNU or BSD                      | Task runner (`Makefile`).                                                    |
| `git`                              | ≥ 2.30                          | History + pre-commit hooks.                                                  |

Optional but recommended:

- [Playwright system deps](https://playwright.dev/docs/cli#install-system-dependencies) (`npx playwright install --with-deps`) — needed for Phase 04 onward to run real browsers.
- [`gitleaks`](https://github.com/gitleaks/gitleaks) ≥ 8.21.4 — the pre-commit hook installs its own copy, but a local CLI is useful for ad-hoc scans.

## Quick install

```bash
git clone <repo>
cd "SENTINEL QA"

# Installs Python deps (uv sync --frozen --all-packages), TS deps
# (pnpm install --frozen-lockfile), and pre-commit hooks.
make install

# Runs the full quality-gate matrix (format-check, lint, typecheck,
# adr-check, tests for both runtimes).
make ci
```

If everything is green, you're set up.

## Per-runtime details

### Python

`uv` will create `.venv/` at the repo root and install:

- The dev tooling (`ruff`, `mypy`, `pytest`, `pytest-cov`, `pytest-asyncio`, `pydantic`, `typer`, `pyyaml`, `pre-commit`) from `[dependency-groups.dev]`.
- The workspace members in editable mode: `packages/python-sdk` (the SDK placeholder) and `apps/cli` (the CLI placeholder).

To activate the venv manually: `source .venv/bin/activate`. But you don't usually need to — `make` targets and `uv run <command>` work without activation.

Lockfile: `uv.lock` (committed). To bump a dep: edit `pyproject.toml`, run `uv lock`, commit the diff.

### TypeScript

`pnpm install --frozen-lockfile` installs dev tooling at the root + workspace members:

- `@sentinelqa/ts-runtime` (Playwright helpers placeholder).
- `@sentinelqa/shared-schema` (JSON Schema sources placeholder).
- `@sentinelqa/mcp-server` (MCP server placeholder).

Lockfile: `pnpm-lock.yaml` (committed). To bump a dep: edit `package.json`, run `pnpm install`, commit the diff.

### Pre-commit hooks

`make install-hooks` runs `pre-commit install --install-hooks`, which wires:

- `pre-commit` stage: trailing-whitespace, end-of-file-fixer, check-yaml/json, check-added-large-files, detect-private-key, check-merge-conflict, check-case-conflict, mixed-line-ending, gitleaks (secret scan), ruff lint + format.
- `commit-msg` stage: commitlint.
- `pre-push` stage: a local `make-ci` hook that runs the full quality matrix before the push completes.

Bypassing hooks with `--no-verify` is forbidden by our engineering rules

### Playwright

Phase 04 brings the Playwright runtime. To prepare your machine for the first browser run:

```bash
pnpm exec playwright install --with-deps chromium
```

CI does this in every TypeScript job (`.github/workflows/ci.yml`), so a stale local cache is the only common gotcha.

## Common make targets

| Target              | What it does                                        |
| ------------------- | --------------------------------------------------- |
| `make help`         | Lists every target.                                 |
| `make install`      | Python + TS + pre-commit hooks.                     |
| `make lint`         | `ruff check .` + `pnpm -r run lint`.                |
| `make format`       | `ruff format .` + Prettier (in-place).              |
| `make format-check` | Both formatters, fail-on-diff.                      |
| `make typecheck`    | `mypy --strict` + `tsc --noEmit` per package.       |
| `make adr-check`    | `scripts/check-adrs.sh`.                            |
| `make test`         | `pytest` + `vitest`.                                |
| `make coverage`     | `pytest --cov` (Phase 01 wires it into `make ci`).  |
| `make ci`           | format-check + lint + typecheck + adr-check + test. |
| `make clean`        | Remove caches and build artifacts.                  |

## Troubleshooting

- **`make install` fails on `uv sync` with a lockfile mismatch.** Someone bumped a dep but did not commit the new `uv.lock`. Run `uv lock` and check in the diff (in a `chore(tooling)` commit if it's a clean re-lock).
- **`make ci` fails on `ruff format --check`.** Run `make format` (or `pnpm exec prettier --write .` for TS/Markdown) and re-stage.
- **Pre-commit complains about `pre-commit-config.yaml` being unstaged.** Stage it (`git add .pre-commit-config.yaml`) and retry.
- **`tsc --noEmit` errors about config files (`vitest.config.ts`, etc.).** They are intentionally outside per-package `tsconfig.include`. ESLint handles them via the `disableTypeChecked` override in `eslint.config.js`. If a new config file fails, add it to the override.
- **macOS BSD `make` complains about a rule.** All Makefile rules are written to be portable across BSD `make 3.81` (macOS default) and GNU `make`. If a target breaks on macOS, that's a bug — file an issue.
- **Pre-commit / gitleaks blocks a commit you believe is safe.** Re-read [`docs/dev/secret-hygiene.md`](./secret-hygiene.md). False positives go in the gitleaks allowlist with an inline comment explaining why; never `--no-verify`.
