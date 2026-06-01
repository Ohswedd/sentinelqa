# SentinelQA — GitHub integration

This folder ships the GitHub-side adapter (the documentation, our engineering rules §39):

- `action.yml` — composite action that installs the runtime, runs `sentinel ci`, uploads artifacts, and publishes SARIF to GitHub code scanning.
- `workflows/sentinel-pr.yml` — reusable workflow that invokes the Action on pull requests and posts the PR comment.
- `post_pr_comment.py` — upsert PR comment helper.

The engine never imports this folder directly ; it's an
adapter behind the existing CLI surface.

## Composite action — `integrations/github/action.yml`

### Inputs

| Name                      | Required | Default                | Notes                                                                              |
| ------------------------- | -------- | ---------------------- | ---------------------------------------------------------------------------------- |
| `url`                     | yes      | —                      | Preview URL. Must be local, staging, or allowlisted (CLAUDE §6, our product spec). |
| `config`                  | no       | `sentinel.config.yaml` | Path to the config file.                                                           |
| `mode`                    | no       | `standard`             | `fast` / `standard` / `full` / `nightly` / `release`.                              |
| `fail-under`              | no       | `''`                   | Override `policy.min_quality_score`; empty inherits config.                        |
| `diff`                    | no       | `''`                   | Git diff range for impacted-tests mode (e.g. `origin/main...HEAD`).                |
| `python-version`          | no       | `3.12`                 | Forwarded to `actions/setup-python`.                                               |
| `node-version`            | no       | `20`                   | Forwarded to `actions/setup-node`.                                                 |
| `sentinelqa-version`      | no       | `''`                   | PyPI version spec; empty skips install (caller pre-installed).                     |
| `install-playwright`      | no       | `true`                 | Run `npx playwright install --with-deps chromium`.                                 |
| `upload-artifacts`        | no       | `true`                 | Upload report.html / findings.json / sarif.json / traces.                          |
| `upload-sarif`            | no       | `true`                 | Upload SARIF to GitHub code scanning.                                              |
| `artifact-name`           | no       | `sentinelqa-report`    | `actions/upload-artifact@v4` name.                                                 |
| `artifact-retention-days` | no       | `14`                   | Retention for uploaded artifacts.                                                  |
| `working-directory`       | no       | `.`                    | Working directory in which to run the audit.                                       |

### Outputs

| Name               | Notes                                                                                  |
| ------------------ | -------------------------------------------------------------------------------------- |
| `quality-score`    | Numeric score (0..100) read from `score.json`.                                         |
| `release-decision` | `pass` / `pass_with_warnings` / `blocked` / `inconclusive` / `unsafe_target_rejected`. |
| `report-html-url`  | Local path to the rendered HTML report. For a public URL, consume the artifact.        |

### Minimal caller workflow

```yaml
name: SentinelQA
on: pull_request: push: branches: [main]

permissions: contents: read pull-requests: write security-events: write

jobs: qa: runs-on: ubuntu-latest steps: - uses: actions/checkout@v4 with: fetch-depth: 0 - uses:./integrations/github with: url: ${{ secrets.PREVIEW_URL }} mode: standard diff: origin/${{ github.base_ref }}...HEAD sentinelqa-version: 0.1.0
```

### Caller workflow — reusable workflow form

```yaml
name: SentinelQA
on: pull_request:

jobs: qa: uses:./integrations/github/workflows/sentinel-pr.yml with: url: ${{ secrets.PREVIEW_URL }} mode: standard secrets: inherit
```

### Mode quick reference

| Mode       | What runs                                                     | When to use                           |
| ---------- | ------------------------------------------------------------- | ------------------------------------- |
| `fast`     | smoke (`@p0`) + diff-aware impacted tests                     | every PR                              |
| `standard` | impacted + required gates (functional, security, a11y)        | default PR                            |
| `full`     | every enabled module, no tag filter                           | nightly / pre-merge of risky branches |
| `nightly`  | full + chaos + extended security probes                       | scheduled nightly                     |
| `release`  | full + tightened quality gate (min score = `max(config, 90)`) | release branches                      |

### Safety notes (our product spec, our engineering rules §6)

- The Action runs `sentinel ci`, which enforces the safety policy before any network activity. Public targets that are not on the allowlist exit with code 4 and emit an audit-log entry.
- The Action never logs `secrets.*`. The `url` input is the only value inlined into the command line, and `sentinel ci` itself redacts that value out of every artifact.
