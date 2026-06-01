# ADR-0031: Example apps — self-contained reference implementations

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

the documentation / §32 require SentinelQA to ship runnable example apps it can
audit in its own CI and demos. Phase 26 delivers that surface: a small
but realistic Next.js + FastAPI stack with two SPA variants (React +
Vite, Django, Flask) plus a deliberately broken Next.js app that drives
the Phase 19 LLM-audit demo (the documentation). The acceptance contract is
`make demo-<name>` for each example and a single `make demo` for the
end-to-end stack.

Two cross-cutting design questions shaped the implementation:

1. **Tooling scope.** Each example needs its own dependencies (Next.js 14, FastAPI 0.115, Django 5, Flask 3, Vite 5). Pulling them into the monorepo's `pnpm` / `uv` workspaces would force the SentinelQA core to track upstream releases on those projects' cadences — and several trip ruff (Django's class-level `dependencies = [...]`), mypy (most examples use loose typing on purpose), Prettier (Vite quote conventions), or coverage (none of these apps execute under CI).
2. **Test depth.** Phase task files mandate one integration test per example. The acceptance criterion for the well-built examples is "score ≥ 85, no critical findings"; for `llm-broken/` it is "≥ 8 distinct LLM-audit findings". Running the full audit against every example in every CI run would require Node, Docker, Playwright browsers, and ~10 minutes of wall clock — too heavy for the default lane.

## Decision

- Each example lives at `examples/<name>/` with its own dependency manifest (`package.json` for the Node examples, `requirements.txt` for the Python examples) and its own checked-in `sentinel.config.yaml`. They are **not** part of the monorepo `pnpm` workspace (`pnpm-workspace.yaml` continues to list only `packages/*` and `apps/dashboard`) and **not** part of the `uv` workspace.
- The root `ruff`, `mypy`, Prettier, ESLint, and coverage scopes explicitly **exclude** `examples/`. Ruff `[tool.ruff].extend-exclude` gains `"examples"`, Prettier ignores it via `.prettierignore`, and `mypy.files` / `coverage.source` were never extended into the tree.
- Top-level Make targets boot each example: - `make demo-flask` / `demo-fastapi` / `demo-django` build a throw-away venv under `examples/<name>/.venv-demo/` and start the app on its documented loopback port. - `make demo-nextjs` / `demo-react-vite` / `demo-llm-broken` run `pnpm install` inside the example then `pnpm run dev`. - `make demo-fastapi-openapi` regenerates `examples/fastapi/openapi.json` from the live FastAPI app. - `make demo` brings up the `examples/end-to-end-demo/docker-compose.yml` stack (FastAPI + Next.js), waits for HTTP, runs `sentinel audit --url http://127.0.0.1:3000 --config examples/nextjs/sentinel.config.yaml --ci`, and leaves the stack up. `make demo-down` tears it down. - Plan documents used `make demo:<name>`; both GNU and BSD `make` treat `:` as the rule separator, so the literal targets use `-`. The change is implementation-level — the deliverable matches.
- Integration tests at `tests/integration/examples/test_<name>.py` are **structural**: - They assert the layout (files exist, `package.json` pins the promised major versions). - They load each example's `sentinel.config.yaml` through the engine config loader so a schema change can't silently invalidate the demo. - They diff routes / decorators against the README so doc drift fails CI before it ships to a user. - `test_llm_broken_findings.py` enumerates the deliberate anti-patterns and fails if fewer than 8 the documentation signals are demonstrated. - `test_end_to_end_demo.py` parses the compose file and asserts the safety contract (loopback-only `ports`, `depends_on` ordering, matching Make targets). - **None** of the tests boot Node, Docker, or Playwright. Booting the full stack against a real audit is a developer-laptop / pre-release smoke flow documented in each README; the CI lane stays fast and hermetic.
- `policy.min_quality_score` is `85` for the well-built examples and `0` for `llm-broken/`: the demo's purpose is to surface findings, and a careless audit would otherwise mark it as passing.

## Consequences

- **Positive:** new contributors can boot any single framework with one Make command and see SentinelQA work end-to-end. The `make demo` stack is a one-line marketing demo. The `llm-broken/` example doubles as a regression suite for Phase 19's LLM-audit module: every commit on `modules/llm_audit/` is implicitly tested against a representative app, not a synthetic JSON fixture.
- **Positive:** because the examples are isolated from the monorepo toolchain, upgrading Next.js / FastAPI / Django / Flask cannot cascade into SentinelQA core CI failures. Each example pins its framework versions in its own manifest.
- **Negative / trade-off:** the default CI lane does **not** prove the examples actually score ≥ 85. The structural tests catch shape drift but not behavioural regressions. The hand-run smoke is the contract reviewers exercise before release.
- **Follow-up obligations:** Phase 29 ("Final Hardening") should add a gated CI lane (`SENTINELQA_HAS_NODE_DOCKER=1`) that brings up the end-to-end stack and asserts the score gate against the Next.js demo. Until then, the score-gate claim stands in each example's README and is reproducible locally.

## Alternatives considered

- **Vendor every example into the monorepo `pnpm` workspace.** Rejected: Next.js / Vite peer-dep churn would force the SentinelQA core toolchain (Prettier 3.4 + ESLint 9.16 + TypeScript 5.7 + the strict workspace `tsconfig`) to track those projects' release cadences. Demos are reference apps, not first-class workspace members.
- **Boot every example in CI per phase task acceptance.** Rejected: each example takes minutes to install + boot; adding seven of them to the default test lane would push wall-clock past ten minutes per CI run, on top of the existing 3 000+ tests. The gated Phase 29 lane is the correct place for that work.
- **Drop the `llm-broken/` example and rely solely on the JSON fixtures under `tests/integration/modules/llm_audit/`.** Rejected: the JSON fixtures prove the rules fire on canonical inputs, but they cannot carry a marketing demo and they don't keep the rules honest against real Next.js source. Shipping a real app forces the rules to handle React's idioms, not a Python tester's idea of them.

## References

- PRD section(s): the documentation (Repository structure), §11.2.1 (Example apps — Phase 26 delivery), §10.9 (LLM-Code Audit), §32 (Recommended Build Order), §27 (Example Generated Test).
- our engineering rules rule(s): our engineering rules(Safety boundary), §14 (Docs), §16 (Testing standard), §17 (Quality gates), §31 (LLM-Code Audit Rules), §34 (Documentation Rules), §42 (Differentiation).
- Related ADRs: ADR-0010 (Discovery), ADR-0024 (LLM-Code audit), ADR-0026 (Visual regression — gated CI lane pattern), ADR-0029 (Plugin architecture).
