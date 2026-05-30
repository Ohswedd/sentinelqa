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
        sdk-api-snapshot \
        build-runner-image \
        demo demo-down \
        demo-flask demo-fastapi demo-fastapi-openapi \
        demo-django demo-nextjs demo-react-vite demo-llm-broken \
        docs docs-build docs-dev docs-gen-all docs-gen-error-codes \
        docs-gen-cli docs-gen-sdk docs-gen-mcp docs-gen-adr-index \
        docs-check-fresh \
        changelog-draft audit-metadata \
        build-all inspect-all \
        bench dod \
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
	@echo "  sdk-api-snapshot  Regenerate the SDK public-API snapshot (Phase 16)"
	@echo "  ci            format-check + lint + typecheck + adr-check + test"
	@echo "  demo          Bring up the end-to-end stack and run sentinel audit"
	@echo "  demo-down     Tear the end-to-end stack down"
	@echo "  demo-<name>   Boot one example: flask|fastapi|django|nextjs|react-vite|llm-broken"
	@echo "  docs          Regenerate auto-generated pages, then build the Starlight site"
	@echo "  docs-dev      Run the Starlight dev server (apps/docs/)"
	@echo "  docs-gen-all  Run every docs generator (CLI / SDK / MCP / errors / ADR index)"
	@echo "  docs-check-fresh  Fail if any generated docs page is stale"
	@echo "  changelog-draft   Draft a Keep a Changelog section from Conventional Commits"
	@echo "  audit-metadata    Verify every publishable manifest carries release-ready metadata"
	@echo "  build-all     Build every Python sdist+wheel and the TS npm tarball into dist/"
	@echo "  inspect-all   Inspect every artifact under dist/ for forbidden contents"
	@echo "  bench         Phase 29 — measure import + CLI cold-start budgets"
	@echo "  dod           Phase 29 — Definition-of-Done sweep (ci + git status)"
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

# --- sdk-api-snapshot ------------------------------------------------------
# Phase 16.06 — regenerate `packages/python-sdk/api-snapshot.json`. CI runs
# `tests/unit/sdk/test_api_snapshot.py` to diff this snapshot against the
# live public surface; drift requires regenerating + an ADR per
# `packages/python-sdk/__deprecation_policy.md`.
sdk-api-snapshot:
	$(UV) run python scripts/dump-sdk-api-snapshot.py

# --- adr-check -------------------------------------------------------------
adr-check:
	scripts/check-adrs.sh

# --- runner image ----------------------------------------------------------
# Phase 08.02 — pinned Playwright base for `sentinel test --docker`. The
# Playwright tag must match the version `packages/ts-runtime` depends on
# (`@playwright/test`). Override with `PLAYWRIGHT_TAG=v… make build-runner-image`.
RUNNER_IMAGE ?= sentinelqa/runner:dev
PLAYWRIGHT_TAG ?= v1.49.0-jammy
build-runner-image:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "docker not on PATH; install Docker Desktop first."; \
		exit 5; \
	fi
	docker build \
		--build-arg PLAYWRIGHT_TAG=$(PLAYWRIGHT_TAG) \
		-t $(RUNNER_IMAGE) \
		-f apps/cli/sentinel/runner/docker/Dockerfile.runner \
		.

# --- examples / demos ------------------------------------------------------
# Phase 26 — example apps. Each demo target builds a throw-away venv (Python
# examples) or runs `pnpm install` (TS examples) and boots the app on a
# loopback port. Targets are intentionally synchronous so `Ctrl-C` cleans up.
# Plan called these `make demo:<name>` — `:` is awkward in Make target names
# across GNU and BSD make, so the literal targets use `-` instead.

demo-flask:
	@cd examples/flask && \
	  if [ ! -d .venv-demo ]; then python3 -m venv .venv-demo; fi && \
	  .venv-demo/bin/pip install -q -r requirements.txt && \
	  .venv-demo/bin/python app.py

demo-fastapi:
	@cd examples/fastapi && \
	  if [ ! -d .venv-demo ]; then python3 -m venv .venv-demo; fi && \
	  .venv-demo/bin/pip install -q -r requirements.txt && \
	  .venv-demo/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

demo-fastapi-openapi:
	@cd examples/fastapi && \
	  if [ ! -d .venv-demo ]; then python3 -m venv .venv-demo; fi && \
	  .venv-demo/bin/pip install -q -r requirements.txt && \
	  .venv-demo/bin/python -c "import json, sys; sys.path.insert(0, '.'); from app.main import app; json.dump(app.openapi(), open('openapi.json', 'w'), indent=2, sort_keys=True); print('wrote openapi.json')"

demo-django:
	@cd examples/django && \
	  if [ ! -d .venv-demo ]; then python3 -m venv .venv-demo; fi && \
	  .venv-demo/bin/pip install -q -r requirements.txt && \
	  .venv-demo/bin/python manage.py migrate --noinput && \
	  .venv-demo/bin/python -c "from django.conf import settings; settings.configure() if not settings.configured else None" 2>/dev/null; \
	  DJANGO_SETTINGS_MODULE=demo_site.settings .venv-demo/bin/python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); U.objects.filter(username='demo').exists() or U.objects.create_user('demo', password='demo'); U.objects.filter(username='admin').exists() or U.objects.create_superuser('admin', '', 'admin')" && \
	  .venv-demo/bin/python manage.py runserver 127.0.0.1:8001

demo-nextjs:
	@cd examples/nextjs && pnpm install && pnpm run dev

demo-react-vite:
	@cd examples/react-vite && pnpm install && pnpm run dev

demo-llm-broken:
	@cd examples/llm-broken && pnpm install && pnpm run dev

# End-to-end stack: FastAPI + Next.js via docker compose, then `sentinel audit`.
# Requires Docker. The audit is non-blocking: the stack stays up until
# `make demo-down` so a human can poke at the report.
demo:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "docker not on PATH; install Docker Desktop first."; \
		exit 5; \
	fi
	cd examples/end-to-end-demo && docker compose up -d
	@echo "Waiting for Next.js to come up on 127.0.0.1:3000…"
	@until curl -sf http://127.0.0.1:3000/ >/dev/null 2>&1; do sleep 2; done
	$(UV) run sentinel audit --url http://127.0.0.1:3000 \
	  --config examples/nextjs/sentinel.config.yaml --ci
	@echo "Audit complete. Stack still running; tear down with 'make demo-down'."

demo-down:
	@if [ -f examples/end-to-end-demo/docker-compose.yml ]; then \
		cd examples/end-to-end-demo && docker compose down -v; \
	fi

# --- docs ------------------------------------------------------------------
# Phase 27 — Astro Starlight site under apps/docs/ + auto-generated pages.
docs-gen-error-codes:
	$(UV) run python -m scripts.docs.gen_error_codes

docs-gen-cli:
	$(UV) run python -m scripts.docs.gen_cli_status

docs-gen-sdk:
	$(UV) run python -m scripts.docs.gen_sdk_reference

docs-gen-mcp:
	$(UV) run python -m scripts.docs.gen_mcp_reference

docs-gen-adr-index:
	$(UV) run python -m scripts.docs.gen_adr_index

docs-gen-all:
	$(UV) run python -m scripts.docs.gen_all

docs-check-fresh:
	$(UV) run pytest tests/integration/docs -q

docs-build: docs-gen-all
	@if [ -f package.json ]; then \
		pnpm --filter @sentinelqa/docs build; \
	else \
		echo "skipping docs build (pnpm workspace not bootstrapped)"; \
	fi

docs-dev: docs-gen-all
	pnpm --filter @sentinelqa/docs dev

docs: docs-build

# --- release ---------------------------------------------------------------
# Phase 28 — audit publishable manifests for release-ready metadata.
audit-metadata:
	$(UV) run python -m scripts.release.audit_metadata

# Phase 28 — build every Python sdist + wheel and the TS npm tarball.
# Pass DIST=<dir> to override the output directory (default: dist/).
# Pass DOCKER=1 to also build the runner image.
DIST ?= dist
DOCKER ?=
build-all:
	$(UV) run python -m scripts.release.build_all \
		--out-dir $(DIST) \
		$(if $(DOCKER),--docker)

# Phase 28 — inspect every built artifact for forbidden contents (.git, .env,
# private keys, cloud credentials, byte-compiled caches). Pass LIST=1 to also
# print the full file inventory of each artifact.
LIST ?=
inspect-all:
	$(UV) run python -m scripts.release.inspect_built_packages \
		--dist-dir $(DIST) \
		$(if $(LIST),--list)

# Phase 28 — draft a Keep a Changelog section from Conventional Commits.
# Writes to CHANGELOG.draft.md for the human curator. Set FROM=<rev> to bound
# the lower edge of the range (default: repo root). VERSION/DATE override the
# header. INCLUDE_INTERNAL=1 surfaces chore/ci/docs/test/build/style commits.
FROM ?=
TO ?= HEAD
VERSION ?= Unreleased
DATE ?=
INCLUDE_INTERNAL ?=
CHANGELOG_DRAFT ?= CHANGELOG.draft.md
changelog-draft:
	$(UV) run python -m scripts.release.draft_changelog \
		$(if $(FROM),--from $(FROM)) \
		--to $(TO) \
		--version $(VERSION) \
		$(if $(DATE),--date $(DATE)) \
		$(if $(INCLUDE_INTERNAL),--include-internal) \
		-o $(CHANGELOG_DRAFT)
	@echo "wrote $(CHANGELOG_DRAFT) (curate by hand before pasting into CHANGELOG.md)"

# Phase 29 — `make bench` measures the Phase 29.04 wall-clock targets and
# writes a JSON report. Pass AUDIT_URL=<url> to additionally measure a live
# `sentinel audit` run; otherwise the audit case is skipped (default).
BENCH_REPEAT ?= 3
BENCH_OUTPUT ?= docs/release/bench-results.json
AUDIT_URL ?=
bench:
	$(UV) run python -m scripts.bench \
		--repeat $(BENCH_REPEAT) \
		--output $(BENCH_OUTPUT) \
		$(if $(AUDIT_URL),--audit-url $(AUDIT_URL))

# Phase 29 — `make dod` runs the local Definition-of-Done sweep (CLAUDE.md
# §18). It is the local equivalent of the phase-gate review: format-check,
# lint, typecheck, adr-check, test, plus the secret-leak audit, plus a
# `git status` cleanliness check. CI itself is `make ci`; this target is
# what a contributor runs before pushing.
dod: ci
	@echo "dod: running secret-leak audit on .sentinel/runs/ ..."
	$(UV) run pytest tests/integration/release/test_secret_leak.py -q
	@echo "dod: running determinism audit ..."
	$(UV) run pytest tests/integration/release/test_determinism.py -q
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "dod: FAIL — git working tree not clean"; \
		git status --porcelain; \
		exit 1; \
	fi
	@echo "dod: PASS — Definition of Done locally satisfied"

# --- ci --------------------------------------------------------------------
ci: format-check lint typecheck adr-check test
	@echo "ci: all gates passed"

# --- clean -----------------------------------------------------------------
clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name .coverage_cache -o -name htmlcov -o -name dist -o -name build -o -name "*.egg-info" \) -prune -exec rm -rf {} +
	rm -f .coverage
