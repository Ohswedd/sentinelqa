<!-- sentinelqa:pr-comment -->

## SentinelQA — RUN\-PASSEDAAAAAA

- **Release decision:** PASS
- **Quality score:** 87.25 / 100
- **Target:** `https://localhost:8080/`
- **Status:** `passed`

### Decision rationale


**Reasons:**
- All gates green; quality\_score=87\.25 \>= min 80\.

### Critical findings

| Severity | Module | Title | ID |
|---|---|---|---|
| High | `security` | Session cookie missing HttpOnly attribute | `FND\-HIGHAAAAAAAA` |

### Changed flows tested

- `functional/login`
- `functional/signup`

### Module summary

| Module | Status | Findings | Duration |
|---|---|---|---|
| `accessibility` | `passed` | 1 | 2100 ms |
| `functional` | `passed` | 0 | 4200 ms |


### Artifacts

- [Full report bundle](https://example.com/run-artifact)

### Suggested next steps

- Ship it. Optional: open follow-ups for info findings.
- See `report.html` for the full breakdown.
