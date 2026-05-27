# SentinelQA — top-level developer task runner.
# Targets are intentionally thin wrappers so CI and humans run the same commands
# (CLAUDE.md §17, §39). Portable across macOS (BSD make 3.81) and Linux (GNU make).

.DEFAULT_GOAL := help

# Prefer uv when available; fall back to python -m for environments without uv.
UV ?= uv

.PHONY: help install install-python install-ts \
        lint lint-py lint-ts \
        format format-py format-ts format-check \
        typecheck typecheck-py typecheck-ts \
        test test-py test-ts \
        coverage \
        adr-check \
        clean ci

help:
	@echo "SentinelQA — make targets"
	@echo "  install       Install Python + TypeScript dev dependencies"
	@echo "  lint          Lint Python and TypeScript"
	@echo "  format        Format Python and TypeScript in place"
	@echo "  format-check  Verify formatting without modifying files (CI mode)"
	@echo "  typecheck     mypy + tsc --noEmit"
	@echo "  test          Run all unit/integration tests"
	@echo "  coverage      Run tests with coverage and enforce the floor"
	@echo "  adr-check     Validate ADR template adherence (wired in Phase 00.07)"
	@echo "  ci            format-check + lint + typecheck + test"
	@echo "  clean         Remove caches and build artifacts"

# --- install ---------------------------------------------------------------
install: install-python install-ts

install-python:
	$(UV) sync --frozen --all-packages

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

# Coverage is opt-in until Phase 01 ships measurable production code.
# Configured floor lives in pyproject.toml ([tool.coverage.report].fail_under).
coverage:
	$(UV) run pytest --cov --cov-report=term-missing

# --- adr-check (wired in Phase 00.07) --------------------------------------
adr-check:
	@if [ -x scripts/check-adrs.sh ]; then \
		scripts/check-adrs.sh; \
	else \
		echo "adr-check script not yet installed (lands in Phase 00.07)"; \
	fi

# --- ci --------------------------------------------------------------------
ci: format-check lint typecheck test
	@echo "ci: all gates passed"

# --- clean -----------------------------------------------------------------
clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name .coverage_cache -o -name htmlcov -o -name dist -o -name build -o -name "*.egg-info" \) -prune -exec rm -rf {} +
	rm -f .coverage
