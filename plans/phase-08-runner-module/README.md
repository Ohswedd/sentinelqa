# Phase 08 — Runner Module

## Objective

Implement the **Runner** (PRD §9.4): execute Playwright tests locally and in Docker, manage workers/shards, collect artifacts, handle retries, and emit module results normalized for the rest of the pipeline.

## PRD / CLAUDE.md references

- PRD §9.4 Runner.
- CLAUDE.md §8 Runtime ownership, §9 Module contract.

## Sub-phases & tasks

1. `01-local-runner.md` — Local Playwright invocation via Phase 04 bridge.
2. `02-docker-runner.md` — Containerized runner with deterministic image.
3. `03-shard-and-workers.md` — Parallelization knobs.
4. `04-retry-and-quarantine.md` — Smart retry with separate quarantine list.
5. `05-result-collection.md` — Translate JSONL stream into `ModuleResult`.
6. `06-runner-cli.md` — `sentinel test` command.
7. `07-runner-tests.md` — Tests + E2E against fixture.

## Definition of Done

- Local runner executes generated tests, captures artifacts, produces a `ModuleResult`.
- Docker runner works with a small canonical image.
- Retries respect config; quarantined tests segregated.
- `sentinel test` end-to-end on fixture app.

## Phase Gate Review

- [ ] Local runner green on fixture.
- [ ] Docker runner image documented + smoke-tested.
- [ ] Retry/quarantine behavior tested.
- [ ] `STATUS.md` updated.
