# Task 00.02 — Python tooling

## Objective

Establish modern, typed Python tooling for every Python package in the monorepo so all later phases can install, lint, typecheck, and test with a single command.

## Prerequisites

- Task 00.01 complete.
- Python 3.11+ available on the developer's machine (document this in `docs/dev/local-setup.md` in task 00.09).

## Deliverables

- Root `pyproject.toml` with workspace metadata, shared dev dependencies (`ruff`, `mypy`, `pytest`, `pytest-cov`, `pytest-asyncio`, `pydantic>=2`, `typer`, `pyyaml`).
- `packages/python-sdk/pyproject.toml` (placeholder; full SDK lands in Phase 16).
- `apps/cli/pyproject.toml` (placeholder; full CLI lands in Phase 02).
- `engine/` and `modules/` exposed as importable Python packages via `pyproject.toml` workspaces or path-based dependencies.
- `ruff.toml` (or `[tool.ruff]` in `pyproject.toml`) with strict rules: pyflakes, pycodestyle, pyupgrade, ruff isort, bugbear, pep8-naming, simplify, return; line length 100.
- `mypy.ini` (or `[tool.mypy]`) with `strict = true`, `warn_unused_ignores = true`, `disallow_untyped_defs = true`, `python_version = 3.11`.
- `pytest.ini` (or `[tool.pytest.ini_options]`) with `testpaths = ["tests"]`, `asyncio_mode = "auto"`, coverage configured at 80% floor.
- `Makefile` (or `Taskfile.yml`) targets: `make install`, `make lint`, `make format`, `make typecheck`, `make test`, `make ci`.
- One trivial smoke test (e.g. `tests/unit/test_smoke.py` asserting `1 + 1 == 2`) so the harness reports green.

## Steps

1. Pick a tooling baseline. Prefer `uv` for fast deterministic installs; fall back to `pip` + `pip-tools` if `uv` is not available. Document the choice in ADR-0001.
2. Write the root `pyproject.toml` declaring the project name `sentinelqa-monorepo`, version `0.0.0`, requires-python `>=3.11`, and a `[tool.uv]` (or equivalent) workspace section listing `apps/cli`, `packages/python-sdk`, and each `engine/*` and `modules/*` sub-package that will be a Python package.
3. Pin dev dependencies explicitly; generate a lockfile (`uv.lock` or `requirements-dev.txt`) and commit it.
4. Configure `ruff` with the rule sets above. Run `ruff check .` and `ruff format .` from a clean state — both must report no issues.
5. Configure `mypy` strictly. Add `py.typed` markers to every Python package directory.
6. Configure `pytest` with the options above. Create `tests/unit/test_smoke.py` with the trivial test and run `pytest` to verify.
7. Write the `Makefile`. Each target must work on macOS and Linux.
8. Run `make ci` (which should chain format-check + lint + typecheck + test) and verify green.

## Acceptance criteria

- `make install` produces a deterministic environment from the committed lockfile.
- `make lint`, `make format`, `make typecheck`, `make test`, `make ci` all succeed.
- `mypy --strict` would fail on any untyped public function — verify by adding a temporary untyped function and watching it fail, then remove.
- Dev dependencies are pinned; no `>=` versions for tools (only for libraries where unavoidable).

## Tests required

- `tests/unit/test_smoke.py`: trivial passing test that proves the harness runs.

## PRD / CLAUDE.md references

- PRD §11.3 Language strategy, §32 Recommended Build Order.
- CLAUDE.md §17 Quality Gates, §20 Python rules.

## Definition of Done

- [ ] Root `pyproject.toml` + lockfile committed.
- [ ] Ruff, mypy, pytest configured at strict settings.
- [ ] `Makefile` targets exist and pass.
- [ ] Smoke test passes.
- [ ] ADR-0001 (or new ADR-0002 if needed) documents the choice of package manager and rule set.
- [ ] Conventional-commit landed (`chore(tooling): set up Python tooling baseline`).
- [ ] `STATUS.md` updated.
