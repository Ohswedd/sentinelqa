<!-- sentinelqa:pr-comment -->

## SentinelQA — RUN\-PASSEDAAAAAA

- **Release decision:** BLOCKED
- **Quality score:** 42.5 / 100
- **Target:** `https://localhost:8080/`
- **Status:** `passed`

### Decision rationale

**Blocked by:**
- `FND\-CRITAAAAAAAA`

**Reasons:**
- Critical finding present\.
- Quality score below minimum \(42\.5 \< 80\)\.

### Critical findings

| Severity | Module | Title | ID |
|---|---|---|---|
| Critical | `security` | Session cookie missing Secure flag | `FND\-CRITAAAAAAAA` |

### Changed flows tested

_Diff-aware mode was not used for this run._

### Module summary

| Module | Status | Findings | Duration |
|---|---|---|---|
| `accessibility` | `passed` | 0 | 2100 ms |
| `functional` | `passed` | 0 | 4200 ms |

### Artifacts

- _Upload the run artifacts to view the full HTML / SARIF report._

### Suggested next steps

- Review every blocker above and fix or downgrade with rationale.
- Re-run `sentinel ci` once fixes land.
