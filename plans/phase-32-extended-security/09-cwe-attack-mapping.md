# Task 32.09 — CWE / ATT&CK / OWASP-API-Top10 mapping

## Deliverables

- `engine/domain/finding.py` gains three optional fields:
  - `cwe_id: str | None` (e.g. `"CWE-347"`)
  - `attack_id: str | None` (MITRE ATT&CK technique, e.g. `"T1606.001"`)
  - `owasp_api_id: str | None` (e.g. `"API-2023-01"`)
- Schema version bumps from `"1"` to `"2"`. The Phase 03 schema
  drift guard updates accordingly; old `"1"` findings are read with
  the new fields absent (forward-compatible).
- `engine/reporter/sarif_writer.py` emits a SARIF `taxa` section
  referencing `cwe.mitre.org` and `attack.mitre.org` when finding
  carries those ids. The standard SARIF v2.1.0 `toolComponent.taxa`
  shape — schema-valid against the vendored SARIF 2.1.0 schema.
- Every existing security finding category gets a default mapping
  (`modules/security/cwe_mapping.py` — single source of truth):
  - headers/missing-csp → CWE-693
  - cookies/missing-httponly → CWE-1004
  - cors/wildcard-with-credentials → CWE-942
  - csrf/missing-token → CWE-352
  - xss/reflected → CWE-79
  - sqli/error-based → CWE-89
  - frontend-secrets → CWE-540
  - idor → CWE-639
- `modules/api/findings.py` gets the same treatment for the API
  module's existing categories.

## Tests required

- `tests/unit/domain/test_finding_schema_v2.py` — round-trip; old v1
  findings parse cleanly; new v2 carries the ids.
- `tests/golden/reports/sarif/` — three new goldens with `taxa`
  references (re-run `make update-goldens` to regenerate).
- `tests/unit/reporter/test_sarif_taxa.py` — `taxa` block validates
  against the vendored SARIF schema.

## Definition of Done

- [ ] Schema bumped to v2; backward-compatible.
- [ ] Every security + API finding has a default CWE.
- [ ] SARIF `taxa` validates.
- [ ] `STATUS.md` updated.
