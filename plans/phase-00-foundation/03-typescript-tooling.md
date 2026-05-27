# Task 00.03 — TypeScript tooling

## Objective

Establish strict TypeScript tooling for every TS package: `packages/ts-runtime`, `packages/mcp-server` (if TS), `packages/shared-schema` (for the JSON Schemas the TS runtime emits), and the future `apps/dashboard`.

## Prerequisites

- Task 00.01 complete.
- Node.js 20+ available; document in `docs/dev/local-setup.md`.

## Deliverables

- Root `package.json` configured as an npm/pnpm workspace declaring `packages/*` and `apps/dashboard`.
- Per-package `package.json` (placeholders) for `packages/ts-runtime`, `packages/shared-schema`, `packages/mcp-server` (mark TS or Python in the README).
- Root `tsconfig.base.json` with `"strict": true`, `"noUncheckedIndexedAccess": true`, `"exactOptionalPropertyTypes": true`, `"noImplicitOverride": true`, `"target": "ES2022"`, `"module": "NodeNext"`.
- Per-package `tsconfig.json` extending the base.
- `.eslintrc.cjs` (or `eslint.config.js` flat config) with `@typescript-eslint/recommended-type-checked`, `eslint-plugin-import`, `eslint-plugin-unicorn` (sane subset).
- `.prettierrc.json` with the team's chosen style (e.g. 100 col, single quotes, trailing commas `all`).
- Playwright dev dep (`@playwright/test`) installed at root; `npx playwright install --with-deps` documented as a one-time setup.
- Smoke test: `packages/ts-runtime/src/__tests__/smoke.test.ts` runs under `vitest` (or `node --test`) and passes.
- `Makefile`/`package.json` script targets: `lint:ts`, `typecheck:ts`, `format:ts`, `test:ts`, all wired into `make ci`.

## Steps

1. Choose pnpm (preferred for speed and disk) or npm workspaces; document in an ADR.
2. Initialize root `package.json` with the chosen workspace declaration; pin Node engine `>=20`.
3. Add `tsconfig.base.json`; verify `tsc --noEmit -p tsconfig.base.json` is a no-op happy path.
4. Install and configure ESLint + Prettier with strict rules; run on the empty repo to confirm zero findings.
5. Pick a test runner — `vitest` is recommended for first-class TS + speed. Wire a smoke test into `packages/ts-runtime`.
6. Update root `Makefile` (from task 00.02) so `make ci` chains the TS gates after the Python gates.
7. Commit on the phase branch.

## Acceptance criteria

- `pnpm install` (or `npm install`) succeeds on a clean clone with no warnings about peer deps.
- `pnpm -r run typecheck`, `pnpm -r run lint`, `pnpm -r run test` all pass.
- Prettier with `--check` finds nothing to change.
- A deliberate `any` in code triggers an ESLint error.

## Tests required

- One TS smoke test in `packages/ts-runtime`.

## PRD / CLAUDE.md references

- PRD §11.3 Language strategy, §15 TypeScript Runtime.
- CLAUDE.md §21 TypeScript / Playwright rules.

## Definition of Done

- [ ] Workspace configured, lockfile committed.
- [ ] Strict TS settings enforced.
- [ ] ESLint + Prettier green on empty repo.
- [ ] Smoke test passes under chosen runner.
- [ ] `make ci` includes TS gates.
- [ ] ADR records the workspace + test runner choice.
- [ ] `STATUS.md` updated.
