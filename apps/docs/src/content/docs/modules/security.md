---
title: Security module
description: Safe HTTP checks, gated probes, dependency + SAST adapters.
status: Stable
---

`sentinel security` runs eleven safe-by-default checks against the
target plus optional dependency / SAST scanners. Destructive probes
are gated by config (`security.mode: authorized_destructive`) AND a
valid proof-of-authorization.

Authority: the documentation, ADR-0018, our engineering rules §6 / §26.

## Default checks

| Check              | What it verifies                                       |
| ------------------ | ------------------------------------------------------ |
| `headers`          | CSP, HSTS, X-Frame-Options, Referrer-Policy presence   |
| `cookies`          | HttpOnly, Secure, SameSite                             |
| `cors`             | Loose `Access-Control-Allow-Origin: *` flagged         |
| `csrf`             | Mutation endpoints reject anonymous POST without token |
| `xss_reflected`    | One safe reflected-XSS probe per form field            |
| `frontend_secrets` | Inline secrets / API keys in bundles                   |
| `deps`             | Dependency advisory scan via configured adapter        |
| `sast`             | Static analysis via configured adapter (opt-in)        |

## Gated checks

| Check        | Required posture                                                |
| ------------ | --------------------------------------------------------------- |
| `xss_stored` | `security.mode=authorized_destructive` + proof-of-authorization |
| `sqli`       | Local target OR destructive + proof-of-authorization            |
| `idor`       | `security.mode=authorized_destructive` + proof-of-authorization |

## Rule IDs

The module ships 23 stable `SEC-*` rule IDs registered with the SARIF
writer. Every finding carries a remediation that is **safe** — no
exploit weaponization, no destructive payload.

## CLI

```bash
uv run sentinel security --url http://127.0.0.1:5001 --checks headers,cookies,cors
```
