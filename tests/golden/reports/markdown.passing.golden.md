# SentinelQA Report — RUN\-PASSEDAAAAAA

**Release decision:** PASS  
**Quality score:** 87.25 / 100

## Summary

- Run ID: `RUN\-PASSEDAAAAAA`
- Target: `https://localhost:8080/` (mode: `safe`)
- Status: `passed`
- Duration: 30.0s
- Modules: `accessibility`, `functional`
- Findings: 1 high, 1 medium, 1 info

## Critical & high-severity findings

- `FND\-HIGHAAAAAAAA` — **High: Session cookie missing HttpOnly attribute** — Evidence: [network\_log](traces/login.har)

## Per-module results

| Module | Status | Findings | Duration |
|---|---|---|---|
| `accessibility` | `passed` | 1 | 2100 ms |
| `functional` | `passed` | 0 | 4200 ms |

## Artifacts

- HTML report: [`report\.html`](report.html) _(generated in Phase 15)_
- Traces, screenshots, and audit log live next to this report.
