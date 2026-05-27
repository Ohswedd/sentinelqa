# Phase 03 — Report Schemas & Reporter Module

## Objective

Define and lock in the **machine-readable schemas** for every artifact SentinelQA emits, plus a small skeleton `Reporter` module that knows how to write them. Real, content-rich reports (HTML template, PR comments, trends) land in Phase 15 — Phase 03 only ensures the wire formats are stable and versioned (CLAUDE §11, §15, §24).

## PRD / CLAUDE.md references

- PRD §18 Data model, §19 Quality scoring, §20 Evidence & reporting, §24 Finding schema (worked example).
- CLAUDE.md §11 Artifact rules, §14 SDK contracts, §15 Agent rules, §17 Quality gates, §24 Findings rules, §38 Report rules.

## Sub-phases & tasks

1. `01-run-json-schema.md` — `run.json` schema + golden test.
2. `02-findings-json-schema.md` — `findings.json` matching PRD §18.2.
3. `03-score-json-schema.md` — `score.json` matching PRD §19.
4. `04-junit-xml.md` — JUnit XML emitter for CI consumers.
5. `05-sarif-export.md` — SARIF 2.1.0 emitter for security findings.
6. `06-markdown-report.md` — minimal Markdown summary used in PR comments.
7. `07-reporter-module.md` — pluggable reporter pipeline.
8. `08-schema-tests.md` — golden + property tests covering every schema.

## Definition of Done

- Every artifact has a JSON Schema in `packages/shared-schema/`, validated in CI.
- The reporter module is registered with the orchestrator and writes the artifacts when called.
- All schemas carry `schema_version` per task 01.07.
- JUnit XML validates against the JUnit XSD.
- SARIF validates against the official 2.1.0 schema.

## Phase Gate Review

- [ ] JSON Schemas present and validated.
- [ ] Golden tests prevent silent schema drift.
- [ ] JUnit + SARIF artifacts validate against external schemas.
- [ ] Reporter module integrated into lifecycle.
- [ ] ADR-0008 (Report schemas & versioning) committed.
- [ ] `STATUS.md` updated.
