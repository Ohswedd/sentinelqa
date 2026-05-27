# Task 05.08 — `sentinel discover` command

## Objective

Wire discovery into the CLI so a user can run `sentinel discover --url …` and get a complete graph + risk map without running modules.

## Deliverables

- Replace the Phase 02 stub of `discover` with the real command.
- Options: `--url`, `--config`, `--max-depth`, `--max-pages`, `--rate-limit`, `--output` (default `<run-dir>`), `--json`.
- The command runs the safety policy, lifecycle steps 1–8 (config, validate, target, safety, run id, artifact dir, snapshot, discover), and writes:
  - `discovery.json` (graph)
  - `forms.json`
  - `api.json`
  - `auth.json`
  - `risk.json`
  - `discovery.report.md` (human summary)
- CLI integration test using a small Vite/Next.js fixture.

## Steps

1. Implement the command.
2. Hook into the lifecycle (steps 1–8 only).
3. Write the human-friendly Markdown summary.
4. Add integration test.

## Acceptance criteria

- `sentinel discover --url http://localhost:5173` against the fixture produces all five files.
- `--json` mode emits one JSON event per artifact and exits 0.

## Tests required

- `tests/integration/cli/test_discover.py`.

## PRD / CLAUDE.md references

- PRD §13 CLI, §9.1.
- CLAUDE.md §13.

## Definition of Done

- [ ] CLI command implemented; lifecycle integration verified.
- [ ] Markdown summary committed as a golden.
- [ ] Tests green.
- [ ] `STATUS.md` updated; Phase 05 ready for gate.
