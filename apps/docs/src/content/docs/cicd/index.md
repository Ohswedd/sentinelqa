---
title: CI/CD
description: Wire SentinelQA into pull requests with the GitHub Action or GitLab template.
status: Stable
---

SentinelQA runs in CI the same way it runs locally — same lifecycle,
same exit codes, same artifacts. The integrations layer adds PR
posting, mode presets, and diff-aware test selection.

.

## Five modes

| Mode       | Selection                                 | Use case                 |
| ---------- | ----------------------------------------- | ------------------------ |
| `fast`     | `@p0` only                                | Per-commit smoke         |
| `standard` | `@p0` + `@p1`                             | Per-PR default           |
| `full`     | Everything                                | Per-PR for risky changes |
| `nightly`  | Full + chaos                              | Scheduled                |
| `release`  | Full + visual baselines + backward-compat | Pre-release              |

`sentinel ci --mode <name>` applies the preset.

## Diff-aware selection

`--diff main..HEAD` translates a git diff into impacted routes /
endpoints / specs via deterministic Next.js (App + Pages Router) +
Vite heuristics. Broad-impact tripwires (lockfile / framework config /
Dockerfile) or > 50 changed files force fallback to `full`.

## GitHub Action

```yaml
- uses: Ohswedd/sentinelqa/integrations/github@main with: url: http://127.0.0.1:3000 mode: standard fail-under: 80 diff: ${{ github.event.pull_request.base.sha }}..${{ github.event.pull_request.head.sha }}
```

Outputs:

- `quality-score`
- `release-decision`
- `report-html-url`

A reusable workflow lives at
`integrations/github/workflows/sentinel-pr.yml`.

## GitLab template

```yaml
include: - project: 'Ohswedd/sentinelqa' file: 'integrations/gitlab/.gitlab-ci.sentinel.yml'

sentinelqa: extends:.sentinelqa variables: SENTINEL_URL: 'http://127.0.0.1:3000' SENTINEL_MODE: 'standard'
```

JUnit and Code Quality reports are uploaded natively.

## PR comments

`integrations/github/post_pr_comment.py` and
`integrations/gitlab/post_mr_note.py` upsert a single SentinelQA
comment per PR via the `<!-- sentinelqa:pr-comment -->` anchor. They
use `urllib` only (no `requests` dep) and retry with exponential
backoff on 429 / 5xx.
