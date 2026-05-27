# Task 04.01 — `packages/ts-runtime` package skeleton

## Objective

Stand up the TypeScript runtime package with strict tooling, a build pipeline, and a placeholder export.

## Deliverables

- `packages/ts-runtime/package.json` declaring:
  - `name`: `@sentinelqa/ts-runtime`.
  - `bin`: `{ "sentinel-ts": "dist/cli.js" }`.
  - `exports`: maps for ESM + types.
  - Dependencies: `@playwright/test`, `zod`, `pino` (or `consola`), `chalk`.
  - Dev: `vitest`, `tsx`, `tsup` (or `tsc --build`).
- `packages/ts-runtime/tsconfig.json` extending root base with `"composite": true`.
- `packages/ts-runtime/src/index.ts` — exports `name`, `version`, placeholder helper.
- `packages/ts-runtime/src/cli.ts` — `sentinel-ts --help / --version` only for now.
- `packages/ts-runtime/tests/smoke.test.ts` — passes.
- `packages/ts-runtime/README.md` — explains the package's contract with Python (links to ADR-0009).

## Steps

1. Initialize the package with the dependencies above.
2. Configure `tsup` (or equivalent) to bundle to `dist/`.
3. Wire `build`, `dev`, `test`, `lint` scripts.
4. Validate `pnpm -r build` produces a runnable `dist/cli.js`.

## Acceptance criteria

- `pnpm --filter @sentinelqa/ts-runtime build` succeeds.
- `node packages/ts-runtime/dist/cli.js --version` prints the version.
- Smoke test green.

## Tests required

- `smoke.test.ts`.

## PRD / CLAUDE.md references

- PRD §11, §15.
- CLAUDE.md §21.

## Definition of Done

- [ ] Package builds and tests.
- [ ] CLI binary runs.
- [ ] `STATUS.md` updated.
