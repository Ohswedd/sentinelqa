# Task 33.02 — OSV vulnerability lookup

## Deliverables

- `modules/supply_chain/osv.py`. Reads the SBOM from task 33.01.
  Batches components into OSV API `POST /v1/querybatch` calls (max
  1000 packages per batch). Network is via `httpx` against
  `api.osv.dev`. Read-only.
- Output `<run_dir>/supply_chain/vulnerabilities.json` schema-versioned
  envelope:
  ```json
  {
    "schema_version": "1",
    "queried_at": "...",
    "components_count": N,
    "vulnerabilities": [
      {
        "package": "lodash",
        "version": "4.17.20",
        "ecosystem": "npm",
        "advisories": [
          { "id": "GHSA-...", "severity": "high", "cwe_ids": ["CWE-..."],
            "fixed_in": "4.17.21", "summary": "..." }
        ]
      }
    ]
  }
  ```
- Each advisory becomes a Finding with `cwe_id` from the advisory,
  `severity` mapped from OSV's `severity[*].score` (CVSS).
- Offline path: when `osv.api.dev` is unreachable, the module emits
  `status: skipped` with a clear reason; the run continues (no fake
  greens).

## Tests required

- `tests/unit/modules/supply_chain/test_osv_parser.py` — fixtures of
  real OSV responses; parser produces the expected envelope.
- `tests/integration/modules/supply_chain/test_osv_mocked.py` — uses
  `httpx.MockTransport`; happy + 429 + 500 + offline.

## Definition of Done

- [ ] Batched + rate-limited calls; respects `target.rate_limit_rps`.
- [ ] Offline degradation is `skipped`, not `errored`, not `passed`.
- [ ] Findings carry `cwe_id` + CVSS-derived `severity`.
- [ ] `STATUS.md` updated.
