# Task 03.04 — JUnit XML emitter

## Objective

Emit a JUnit-compatible XML report so any CI provider (GitHub Actions, GitLab, Jenkins) can ingest SentinelQA results out of the box.

## Deliverables

- `engine/reporter/junit_writer.py` exposing `write_junit(dir, run, findings, module_results) -> Path`.
- Each module becomes a `<testsuite>`; each finding (or test failure) becomes a `<testcase>`.
- Use the widely-supported subset of the JUnit XML schema (Surefire). Validate output against the public JUnit XSD (`tests/golden/reports/junit.xsd`).
- Standard attributes: `name`, `classname`, `time` (seconds), `failures`, `errors`, `tests`. Include `<system-out>` with the redacted log excerpt when available.

## Steps

1. Implement the writer using `xml.etree.ElementTree` (no external dep).
2. Use Python's `defusedxml` only if parsing externally — for writing, stdlib is fine.
3. Add `tests/golden/reports/junit/` with goldens.
4. CI step: validate emitted XML against the JUnit XSD using `xmllint` or `lxml`.

## Acceptance criteria

- Validates against the JUnit XSD.
- GitHub Actions' `actions/upload-artifact` + JUnit reporter (e.g. `dorny/test-reporter`) consume it cleanly in a smoke test.

## Tests required

- `tests/golden/reports/test_junit_xml.py`.
- `tests/integration/ci/test_junit_xsd.py` (skipped if `xmllint`/`lxml` missing).

## PRD / CLAUDE.md references

- PRD §21 CI/CD.
- CLAUDE.md §38 Report rules.

## Definition of Done

- [ ] Writer emits valid JUnit XML.
- [ ] XSD validation green.
- [ ] Goldens locked.
- [ ] `STATUS.md` updated.
