# Task 03.05 — SARIF 2.1.0 emitter

## Objective

Emit a SARIF 2.1.0 file for security-relevant findings so GitHub's code-scanning UI and other security tools can ingest them (PRD §10.7, §21).

## Deliverables

- `engine/reporter/sarif_writer.py` exposing `write_sarif(dir, findings, run) -> Path`.
- Output validates against the official SARIF 2.1.0 schema (`packages/shared-schema/sarif-2.1.0.json` — committed copy of the official schema).
- Mapping rules from `Finding` → SARIF result:
  - `ruleId` from `finding.id` prefix (e.g. `SEC-001` becomes a rule `SEC-001` with `helpUri` pointing at our docs).
  - `level`: `error` for critical/high, `warning` for medium, `note` for low/info.
  - `message.text` from `finding.title` + `finding.description`.
  - `locations[]` from `finding.location` (artifact URI = file path; region = line/column when known).
  - `properties` carries `confidence`, `severity`, `category`.
- A rule registry: `engine/reporter/sarif_rules.py` lists every known rule id with title, description, helpUri. Rules are dynamic — module phases register their rules.

## Steps

1. Vendor the official SARIF 2.1.0 schema. Commit it under `packages/shared-schema/external/`.
2. Implement the writer with redaction and the mapping rules.
3. Implement rule registration.
4. Add goldens including: empty SARIF, single critical, mixed severities.
5. Validate goldens against the schema in CI.

## Acceptance criteria

- All goldens validate.
- GitHub `github/codeql-action/upload-sarif` smoke test accepts the file (verified later in Phase 17).

## Tests required

- `tests/golden/reports/test_sarif.py`.
- `tests/integration/reporter/test_sarif_schema_validation.py`.

## PRD / CLAUDE.md references

- PRD §10.7 Security, §21 CI/CD.
- CLAUDE.md §26 Security module rules, §38 Report rules.

## Definition of Done

- [ ] SARIF emitter implemented and tested.
- [ ] Schema validation green.
- [ ] Rule registry mechanism in place.
- [ ] `STATUS.md` updated.
