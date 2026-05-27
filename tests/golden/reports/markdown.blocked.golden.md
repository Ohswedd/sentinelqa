# SentinelQA Report — RUN\-PASSEDAAAAAA

**Release decision:** BLOCKED  
**Quality score:** 42.5 / 100

## Summary

- Run ID: `RUN\-PASSEDAAAAAA`
- Target: `https://localhost:8080/` (mode: `safe`)
- Status: `passed`
- Duration: 30.0s
- Modules: `accessibility`, `functional`, `performance`
- Findings: 1 critical

## Critical & high-severity findings

- `FND\-CRITAAAAAAAA` — **Critical: Session cookie missing Secure flag** — Evidence: [network\_log](traces/login.har)

## Per-module results

| Module | Status | Findings | Duration |
|---|---|---|---|
| `accessibility` | `errored` | 0 | 300 ms |
| `functional` | `failed` | 0 | 5200 ms |
| `performance` | `skipped` | 0 | 0 ms |

## Artifacts

- HTML report: [`report\.html`](report.html) _(generated in Phase 15)_
- Traces, screenshots, and audit log live next to this report.
