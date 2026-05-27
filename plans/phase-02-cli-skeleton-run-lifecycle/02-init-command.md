# Task 02.02 — `sentinel init` command

## Objective

Implement `sentinel init` so a brand-new user gets a working `sentinel.config.yaml`, `tests/sentinel/` directory, `.sentinel/` runtime tree, `.gitignore` patch, and a starter GitHub Action — all without prompts when `--ci`.

## Prerequisites

- Task 02.01 complete.

## Deliverables

Writes (idempotent, never overwrites without `--force`):

- `sentinel.config.yaml` — generated from `engine.config.dump_config()` with detected framework, package manager, and base URL when possible.
- `tests/sentinel/.gitkeep` (or `README.md` if helpful).
- `.sentinel/.gitignore` (entries: `runs/`, `cache/`, `reports/`, `baselines/`).
- `.github/workflows/sentinel.yml` — minimal CI invoking `sentinel ci` (template from PRD §21.1).
- Adds entries to root `.gitignore` if missing: `.sentinel/runs/`, `.sentinel/cache/`, `.sentinel/reports/`.
- Echoes a "next steps" message pointing at `sentinel doctor` then `sentinel audit --url <BASE_URL>`.

Detection helpers (`apps/cli/sentinel/init_detect.py`):

- Framework detection by inspecting files: `next.config.*` → `nextjs`, `vite.config.*` → `vite`, `package.json` engines + scripts, Python `pyproject.toml` tools (`fastapi`, `django`, `flask`).
- Package manager: prefer `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `package-lock.json` → npm.
- Existing Playwright install: presence of `@playwright/test` in deps.

## Steps

1. Implement detection helpers; each returns `None` when uncertain. Never guess silently — log decisions in `--verbose`.
2. Implement `init` command. Read flags: `--path .`, `--force`, `--non-interactive`.
3. Build the YAML using `dump_config()` and write it. Strip any field that has no detected value (the loader's safe defaults will fill them in at load time).
4. Write the GitHub Action template from PRD §21.1 (use the exact YAML there).
5. Patch `.gitignore` only if entries are missing; never duplicate.
6. Print a friendly summary in human mode; emit one JSON object in `--json` mode.

## Acceptance criteria

- `sentinel init --ci` in an empty directory produces a config that `load_config()` accepts.
- Re-running `sentinel init` without `--force` is a no-op (exits 0 with `nothing to do`).
- With `--force`, files are overwritten and a diff is shown in `--verbose`.

## Tests required

- `tests/integration/cli/test_init.py` — fresh repo, partial repo (only `package.json`), repo with existing `sentinel.config.yaml`.
- Idempotency test: run twice, no file changes the second time.
- Force-overwrite test.

## PRD / CLAUDE.md references

- PRD §12.1 First-time setup, §17 Configuration, §21.1 GitHub Action template.
- CLAUDE.md §13 CLI rules.

## Definition of Done

- [ ] Detection helpers covered by tests.
- [ ] Init command idempotent and `--force` safe.
- [ ] GitHub Action template matches PRD §21.1.
- [ ] `STATUS.md` updated.
