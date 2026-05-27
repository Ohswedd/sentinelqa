# Task 03.01 — `run.json` schema

## Objective

Define the canonical wire format for a SentinelQA run summary.

## Deliverables

- `packages/shared-schema/run.schema.json` (JSON Schema draft 2020-12). Required fields:
  - `schema_version` (string, "1").
  - `run_id` (string).
  - `started_at` / `finished_at` (RFC 3339 UTC).
  - `status` (`passed`|`failed`|`incomplete`|`unsafe_blocked`|`dry_run`).
  - `target` ({ base_url, host, mode }).
  - `config_digest` (sha256 of canonicalized config snapshot).
  - `modules_run` (array of module names).
  - `release_decision` (one of PRD §19.3).
  - `quality_score` (number 0–100; `null` if `unsafe_blocked` or `dry_run`).
  - `summary` ({ passed, failed, blocked, info }).
  - `artifact_paths` ({ findings, score, junit, sarif, report_html, report_md, audit_log }).
  - `errors` (array of `{ code, message }` with redaction applied).
- `engine/reporter/run_writer.py` exposing `write_run(dir: ArtifactDirectory, run: TestRun) -> Path`.
- A golden fixture: `tests/golden/reports/run.passed.golden.json`, `run.unsafe.golden.json`, `run.dry_run.golden.json`.

## Steps

1. Author the JSON Schema; validate it with `check-jsonschema --check-metaschema`.
2. Build `write_run()` to serialize a `TestRun` to the schema (applying redaction).
3. Add golden tests: build a known `TestRun`, write it, compare byte-for-byte after canonical JSON formatting (`json.dumps(..., sort_keys=True, indent=2)`).
4. Add `make update-goldens` integration.

## Acceptance criteria

- Schema validates the goldens.
- `write_run()` is idempotent for the same input.
- `config_digest` is reproducible.

## Tests required

- `tests/golden/reports/test_run_json.py`.
- `tests/unit/reporter/test_run_writer.py`.

## PRD / CLAUDE.md references

- PRD §18, §20.
- CLAUDE.md §11, §38.

## Definition of Done

- [ ] Schema + writer + goldens committed.
- [ ] Schema CI check passes.
- [ ] `STATUS.md` updated.
