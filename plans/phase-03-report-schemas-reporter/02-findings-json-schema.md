# Task 03.02 — `findings.json` schema

## Objective

Define the canonical schema for findings, matching PRD §18.2 and CLAUDE §24, with strict redaction.

## Deliverables

- `packages/shared-schema/findings.schema.json`:
  - Root: `{ schema_version, run_id, generated_at, count, findings: [...] }`.
  - Each finding: `id`, `run_id`, `module`, `category`, `severity` (enum), `confidence` (0–1), `title`, `description`, `location` ({ route?, file?, selector?, line? }), `evidence` (array of `{ type, path, redacted: true }`), `reproduction_steps` (string[]), `recommendation`, `created_at`, `affected_target`, `schema_version`.
- `engine/reporter/findings_writer.py` exposing `write_findings(dir, findings) -> Path`.
- Goldens covering: empty, one critical, mixed severities, redaction examples (a finding with a redacted token in description must be saved with `[REDACTED:bearer_token]`).
- A linter `engine/reporter/findings_linter.py` that flags vague findings (`title` length < 8 chars, or description containing the words "issue found", "error", "problem" without specifics). Used by Phase 24 plugin contract review.

## Steps

1. Author and validate the schema.
2. Build the writer with redaction.
3. Build the vague-finding linter and call it from the writer (emit a `LinterWarning` in the run but don't fail).
4. Write goldens and tests.

## Acceptance criteria

- Schema rejects findings without evidence (PRD §20 says "every failure must have at least one evidence artifact" — this writer enforces it for severity ≥ medium).
- Linter flags "Security issue found." as vague.

## Tests required

- `tests/golden/reports/test_findings_json.py`.
- `tests/unit/reporter/test_findings_linter.py`.

## PRD / CLAUDE.md references

- PRD §18.2, §20, §24.
- CLAUDE.md §24 Findings rules.

## Definition of Done

- [ ] Schema + writer + linter + goldens committed.
- [ ] Linter exercised by tests.
- [ ] `STATUS.md` updated.
