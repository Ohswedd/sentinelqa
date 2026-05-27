# Task 02.05 — Artifact tree & persistence

## Objective

Implement the run artifact layout from CLAUDE §11. Every run gets a fully-isolated directory containing every machine-readable and human-readable output, evidence, and audit trail.

## Prerequisites

- Task 02.04 complete.

## Deliverables

- `engine/orchestrator/artifacts.py` exposing:
  - `class ArtifactDirectory` with methods `create(run_id) -> Path`, `path(name: str) -> Path`, `write_json(name, obj)`, `write_yaml(name, obj)`, `write_text(name, text)`, `subdir(name) -> Path`.
- The directory layout matches CLAUDE §11:
  ```
  .sentinel/runs/<run-id>/
    run.json
    config.snapshot.yaml
    findings.json
    score.json
    report.html
    report.md
    junit.xml
    sarif.json
    traces/
    screenshots/
    videos/
    logs/
    audit.log
  ```
  Files are created on demand; the empty placeholders are NOT created proactively (CLAUDE §11 says "when available").
- `engine/orchestrator/retention.py` — pruning helper:
  - `prune_old_runs(root: Path, keep_last: int, max_age_days: int)`.
  - Never deletes runs flagged with `keep: true` in `run.json`.
- `engine/orchestrator/symlinks.py` — maintain `.sentinel/runs/latest` symlink (or copy on Windows) pointing at the newest run.
- Cross-platform path handling via `pathlib`.
- All writes go through `redact()` before JSON serialization.

## Steps

1. Implement the directory class with atomic writes (write to `*.tmp`, fsync, rename).
2. Implement retention helper. Add `make prune-runs` for developer convenience.
3. Implement the latest pointer (symlink on POSIX, junction or marker file on Windows).
4. Wire it into the lifecycle from task 02.04.

## Acceptance criteria

- A fresh run creates only the files actually written; no empty placeholders.
- `.sentinel/runs/latest` always points at the newest run.
- `prune_old_runs(keep_last=10, max_age_days=30)` deletes only old, non-pinned runs.
- Atomic writes never leave half-written JSON behind.

## Tests required

- `tests/integration/orchestrator/test_artifacts.py` — create, read back, atomicity (kill mid-write via mock).
- `tests/integration/orchestrator/test_retention.py`.
- `tests/integration/orchestrator/test_latest_symlink.py`.

## PRD / CLAUDE.md references

- PRD §10 / §20 (artifact + evidence rules).
- CLAUDE.md §11 Artifact and Data Rules.

## Definition of Done

- [ ] Layout matches CLAUDE §11.
- [ ] Atomic writes verified.
- [ ] Retention + latest pointer working.
- [ ] `STATUS.md` updated.
