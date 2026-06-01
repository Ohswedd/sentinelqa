---
title: Discovery module
description: HTTP-first + Playwright crawler that builds a typed map of the app under test.
status: Stable
---

The discovery module is the first stop in an audit: it crawls the
target, builds a typed model of routes / DOM elements / forms / APIs /
auth boundaries, and writes `discovery.json` + `forms.json` +
`api.json` + `auth.json` + `risk.json` + `discovery.report.md`.

.

## Backends

| Engine           | When to use                                             |
| ---------------- | ------------------------------------------------------- |
| `http` (default) | Server-rendered apps; deterministic; cheap              |
| `playwright`     | Client-rendered SPAs; requires `sentinel-ts` + Chromium |

Configure via `discovery.engine` in `sentinel.config.yaml`.

## What it captures

- **DOM map** — element types, missing labels, repeated components, unreachable links.
- **Forms inventory** — fields, validation hints, reCAPTCHA flag.
- **API surface** — path templating (`[id]`, `[uuid]`, `[hex]`), 5xx detection, JS-bundle-only references.
- **Auth boundary** — anonymous + authenticated passes, UI-only-auth hints, escalation hints, env-var-name-only artifacts.
- **OpenAPI / GraphQL ingest** — 3.x JSON/YAML/URL + SDL + introspection.
- **Risk map** — ten deterministic rules, deterministic ordering.

## Safety

Discovery respects `robots.txt`, sends a transparent
`SentinelQA/<version>` UA + `X-SentinelQA-Test-Run: <run-id>`
header, and is rate-limited by a token bucket. There is no stealth
mode.

## CLI

```bash
uv run sentinel discover --url http://127.0.0.1:5001
```
