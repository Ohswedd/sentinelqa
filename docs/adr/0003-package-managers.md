# ADR-0003: Package managers (uv + pnpm)

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

Two runtimes (ADR-0002) need deterministic installs, fast cold starts on CI, monorepo-aware workspace handling, and a single lockfile per ecosystem that humans actually read. our engineering rules; the documentation implies that "install + lint + typecheck + test" must be a one-shot, repeatable command. The choice of package managers fixes the baseline ergonomics of every future phase.

We also need to decide how the coverage floor interacts with a Phase-00 codebase that ships no production code: enforcing 80% coverage on an empty source tree would either always-fail or be vacuously satisfied.

## Decision

- **Python:** `uv` (Astral) as the package manager + lockfile generator. Pin `uv ==0.5.24` in CI; declare workspace members in `pyproject.toml#[tool.uv.workspace]`.
- **TypeScript:** `pnpm` (workspaces). Pin `pnpm@9.15.4` via `packageManager` in the root `package.json`; declare workspaces in `pnpm-workspace.yaml`.
- **Workspace membership grows phase by phase.** Phase 00 lists only `apps/cli` and `packages/python-sdk` (Python) and `packages/{ts-runtime,shared-schema,mcp-server}` + `apps/dashboard` (TS) as workspace members. When `engine/policy`, `engine/orchestrator`, etc. gain their first `.py` files, the phase that adds them also adds their `pyproject.toml` and lists them as workspace members. mypy `files = [...]` and ruff `src = [...]` follow the same growth pattern.
- **Lockfiles are committed.** `uv.lock` and `pnpm-lock.yaml` are required to land in every PR that bumps a dependency.
- **Coverage floor is configured but not yet enforced.** `[tool.coverage.report] fail_under = 80` is set in `pyproject.toml`. `make test` runs pytest without coverage; `make coverage` opt-ins and enforces the floor; `make ci` does NOT depend on `make coverage` until Phase 01 ships measurable production code (the first such code is the redaction implementation in Phase 01.05). At that point a follow-up commit wires `make ci` → `make coverage` and we lock the floor.

## Consequences

- **Positive:** `uv sync --frozen --all-packages` produces a deterministic Python env in seconds, including all workspace members in editable mode. `pnpm install --frozen-lockfile` does the same on the TS side. CI cache hits are large.
- **Positive:** Lockfiles are reviewable artifacts; dependency drift is visible in PR diffs.
- **Negative / trade-off:** Two lockfiles, two package managers. Mitigated by the `Makefile` wrapping both into one `make install` / `make ci`.
- **Negative / trade-off:** Coverage gate is configured-but-soft today. Mitigated by Phase 01 owning the flip, with the trigger date already pegged to "first redaction commit." If Phase 01 lands without enabling the gate, the phase gate review fails.
- **Follow-up obligations:** Phase 01.05 enables `make coverage` inside `make ci` and pins the floor at 80. Every subsequent phase that adds a new package must also add it to the coverage `source = [...]` list.

## Alternatives considered

- **`poetry` + `npm`** — both work, both more widely-known. Rejected: `uv` is ~10× faster on cold installs (matters for CI matrix runs); `pnpm` workspaces are dramatically more disk-efficient than npm's nested `node_modules` and produce smaller PR-diff lockfile noise.
- **`pip-tools` + `npm`** — would also work. Rejected for the same speed/efficiency reasons; also `pip-tools` doesn't model workspaces natively, so the cross-package editable install would require a wrapper script.
- **Enforce coverage floor at Phase 00 by excluding the empty source dirs.** Rejected: gaming the floor (running coverage on test files only) earns a 100% number that means nothing. A flag-day flip at the first real code commit is honest and easy to audit.

## References

- the documentation Language strategy, §32 Recommended Build Order.
- our engineering rules§35 Dependency Rules.
- External: <https://docs.astral.sh/uv/>, <https://pnpm.io/workspaces>.
- Related ADRs: ADR-0001 (repository structure), ADR-0002 (language strategy).
