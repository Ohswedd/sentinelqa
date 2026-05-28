# SentinelQA — top-level developer task runner.
# Targets are intentionally thin wrappers so CI and humans run the same commands
# (CLAUDE.md §17, §39). Portable across macOS (BSD make 3.81) and Linux (GNU make).

.DEFAULT_GOAL := help

# Prefer uv when available; fall back to python -m for environments without uv.
UV ?= uv

.PHONY: help install install-python install-ts install-hooks \
        lint lint-py lint-ts \
        format format-py format-ts format-check \
        typecheck typecheck-py typecheck-ts \
        test test-py test-ts test-fast test-full \
        coverage \
        adr-check \
        schemas update-goldens \
        clean ci

help:
	@echo "SentinelQA — make targets"
	@echo "  install       Install Python + TypeScript dev dependencies"
	@echo "  lint          Lint Python and TypeScript"
	@echo "  format        Format Python and TypeScript in place"
	@echo "  format-check  Verify formatting without modifying files (CI mode)"
	@echo "  typecheck     mypy + tsc --noEmit"
	@echo "  test          Run default tests (slow/bench markers excluded)"
	@echo "  test-fast     Alias for test"
	@echo "  test-full     Include slow + bench tests (property + perf)"
	@echo "  coverage      Run tests with coverage and enforce the floor"
	@echo "  adr-check     Validate ADR template adherence"
	@echo "  schemas       Emit JSON Schemas for every engine.domain model"
	@echo "  update-goldens  Regenerate report goldens (Phase 03+); commit the diff"
	@echo "  ci            format-check + lint + typecheck + adr-check + test"
	@echo "  clean         Remove caches and build artifacts"

# --- install ---------------------------------------------------------------
install: install-python install-ts install-hooks

install-python:
	$(UV) sync --frozen --all-packages

install-hooks:
	@if [ -f .pre-commit-config.yaml ]; then \
		$(UV) run pre-commit install --install-hooks; \
	else \
		echo "skipping pre-commit install (.pre-commit-config.yaml not yet present)"; \
	fi

install-ts:
	@if [ -f package.json ]; then \
		pnpm install --frozen-lockfile; \
	else \
		echo "skipping TS install (package.json lands in Phase 00.03)"; \
	fi

# --- lint ------------------------------------------------------------------
lint: lint-py lint-ts

lint-py:
	$(UV) run ruff check .

lint-ts:
	@if [ -f package.json ]; then \
		pnpm -r run lint; \
	else \
		echo "skipping TS lint (package.json lands in Phase 00.03)"; \
	fi

# --- format ----------------------------------------------------------------
format: format-py format-ts

format-py:
	$(UV) run ruff format .

format-ts:
	@if [ -f package.json ]; then \
		pnpm -r run format; \
	else \
		echo "skipping TS format (package.json lands in Phase 00.03)"; \
	fi

format-check:
	$(UV) run ruff format --check .
	@if [ -f package.json ]; then \
		pnpm exec prettier --check .; \
	fi

# --- typecheck -------------------------------------------------------------
typecheck: typecheck-py typecheck-ts

typecheck-py:
	$(UV) run mypy

typecheck-ts:
	@if [ -f package.json ]; then \
		pnpm -r run typecheck; \
	else \
		echo "skipping TS typecheck (package.json lands in Phase 00.03)"; \
	fi

# --- test ------------------------------------------------------------------
test: test-py test-ts

test-py:
	$(UV) run pytest

test-ts:
	@if [ -f package.json ]; then \
		pnpm -r run test; \
	else \
		echo "skipping TS test (package.json lands in Phase 00.03)"; \
	fi

# Phase 01: coverage floor is enforced; fail_under lives in pyproject.toml.
coverage:
	$(UV) run pytest --cov --cov-report=term-missing

# `test` already excludes `slow` and `bench` markers via pyproject; alias as
# `test-fast` for symmetry with `test-full`.
test-fast: test-py

test-full:
	$(UV) run pytest --override-ini="addopts=-ra --strict-config --strict-markers --import-mode=importlib"

# Generate JSON Schemas for every domain model into packages/shared-schema/.
# Also re-export the redaction ruleset the TS runtime mirrors (Phase 04).
schemas:
	$(UV) run python -c "from pathlib import Path; from engine.domain.jsonschema import dump_schemas; written = dump_schemas(Path('packages/shared-schema/schemas')); [print(p) for p in written]"
	$(UV) run python scripts/export-redaction-rules.py
	$(UV) run python scripts/export-redaction-parity.py
	$(UV) run python scripts/export-ts-events-parity.py

# Phase 03: rewrite report goldens in place. Reviewer sees the diff in the
# follow-up commit — the only place schema drift may originate.
# Prompts for confirmation; pass FORCE=1 to skip the prompt (CI use only).
update-goldens:
	@if [ -z "$$FORCE" ]; then \
		printf "About to rewrite tests/golden/reports/ in place.\n"; \
		printf "Diff the result and commit deliberately.\n"; \
		printf "Continue? [y/N] "; \
		read ans; \
		case "$$ans" in y|Y|yes|YES) ;; *) echo "aborted."; exit 1 ;; esac; \
	fi
	SENTINELQA_UPDATE_GOLDENS=1 $(UV) run pytest tests/golden -p no:cacheprovider

# --- adr-check -------------------------------------------------------------
adr-check:
	scripts/check-adrs.sh

# --- ci --------------------------------------------------------------------
ci: format-check lint typecheck adr-check test
	@echo "ci: all gates passed"

# --- clean -----------------------------------------------------------------
clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name .coverage_cache -o -name htmlcov -o -name dist -o -name build -o -name "*.egg-info" \) -prune -exec rm -rf {} +
	rm -f .coverage
