# Task 03.07 — Reporter module skeleton

## Objective

Wire the writers into a small Reporter module that the run lifecycle invokes during step 15 (`generate_reports`). Concrete formats are decided by the config (`report.formats`).

## Deliverables

- `engine/reporter/__init__.py` exposing `Reporter` class with method `emit(run, findings, score, policy, formats: list[str]) -> dict[str, Path]`.
- The reporter dispatches to: `run_writer`, `findings_writer`, `score_writer`, `junit_writer`, `sarif_writer`, `markdown_writer`. Each is optional; only formats listed in config are produced.
- A `ReporterPlugin` interface stub for Phase 24 (plugins).
- Registration with the orchestrator (`engine/orchestrator/registry.py`) so step 15 calls the reporter.
- An audit-log entry per emitted artifact.

## Steps

1. Implement the dispatcher.
2. Register hook with the orchestrator.
3. Add an integration test running the full lifecycle and verifying every requested artifact appears in `.sentinel/runs/<id>/`.

## Acceptance criteria

- All requested formats produced.
- Disabling a format in config skips its writer.
- Audit log lists every emitted artifact.

## Tests required

- `tests/integration/reporter/test_reporter_dispatch.py`.

## PRD / CLAUDE.md references

- PRD §9.7 Reporter, §17 Config.
- CLAUDE.md §11 Artifact rules, §38 Report rules.

## Definition of Done

- [ ] Reporter wired into lifecycle.
- [ ] Format dispatch tested.
- [ ] `STATUS.md` updated.
