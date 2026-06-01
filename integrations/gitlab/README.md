# SentinelQA — GitLab integration

GitLab-side adapter (the documentation, our engineering rules §39):

- `.gitlab-ci.sentinel.yml` — drop-in include with a `.sentinelqa` job template; reusable via `extends:`.
- `post_mr_note.py` — upsert merge-request note helper.

The engine never imports this folder ; it's an adapter
behind the existing CLI.

## Drop-in include

```yaml
include: - project: 'sentinelqa/sentinelqa' file: '/integrations/gitlab/.gitlab-ci.sentinel.yml'

sentinelqa: extends:.sentinelqa variables: SENTINELQA_URL: 'https://preview-${CI_COMMIT_SHORT_SHA}.example.com' SENTINELQA_MODE: 'standard' SENTINELQA_DIFF: 'origin/main...HEAD' SENTINELQA_VERSION: '0.1.0'
```

### Job variables

| Variable                | Default    | Notes                                                       |
| ----------------------- | ---------- | ----------------------------------------------------------- |
| `SENTINELQA_URL`        | _(empty)_  | Required preview URL.                                       |
| `SENTINELQA_MODE`       | `standard` | `fast` / `standard` / `full` / `nightly` / `release`.       |
| `SENTINELQA_DIFF`       | _(empty)_  | Git diff range; empty disables diff-aware selection.        |
| `SENTINELQA_FAIL_UNDER` | _(empty)_  | Override `policy.min_quality_score`; empty inherits config. |
| `SENTINELQA_VERSION`    | _(empty)_  | PyPI version spec; empty skips `pip install`.               |
| `PYTHON_VERSION`        | `3.12`     | Docker image tag.                                           |
| `NODE_VERSION`          | `20`       | Node.js major version.                                      |

### MR comment

The job posts a SentinelQA summary back to the merge request when both
`CI_MERGE_REQUEST_IID` and `SENTINELQA_GITLAB_TOKEN` are present. The
token must be a project access token (or group access token) with the
`api` scope, set as a masked + protected CI variable.

### Artifacts

`.sentinel/runs/*/{run.json, findings.json, score.json, report.html,
report.md, sarif.json, junit.xml, traces/**, screenshots/**, videos/**}`
are uploaded for 14 days; JUnit XML is consumed by GitLab's native test
reporting; `findings.json` is consumed as a Code Quality report.

### Safety boundary (our product spec, our engineering rules §6)

- `sentinel ci` enforces the safety policy before any network I/O. Public targets that are not on the allowlist exit code 4 and emit an audit-log entry.
- The job body never logs `SENTINELQA_GITLAB_TOKEN`; the poster reads it directly from the environment, never echoes it.
