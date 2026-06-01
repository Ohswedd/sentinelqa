# SentinelQA Next.js example

A Next.js 14 app (App Router) with cookie-based session auth, an
in-memory CRUD for the "Project" entity, and an `/admin` page gated on
the `admin` role. SentinelQA Phase 26.01.

## Run

From the repo root:

```bash
make demo-nextjs
```

The Make target runs `pnpm install` inside `examples/nextjs/` and starts
the Next.js dev server on `http://127.0.0.1:3000`.

Or, manually:

```bash
cd examples/nextjs
pnpm install
pnpm run dev
```

## Credentials

Local demo only — **do not deploy this app**.

| Username | Password | Role |
| --- | --- | --- |
| `demo` | `demo` | `user` |
| `admin` | `admin` | `admin` |

## Audit it

With the app running:

```bash
sentinel audit --url http://127.0.0.1:3000 \ --config examples/nextjs/sentinel.config.yaml
```

The provided config sets `policy.min_quality_score: 85` and runs the
discovery / functional / accessibility / performance / safe-security /
llm-audit modules.

## Routes

| Path | Auth | Notes |
| --- | --- | --- |
| `/` | No | Landing page. |
| `/login` | No | Server-action login form. |
| `/signup` | No | Disabled in this demo — placeholder copy. |
| `/dashboard` | Yes | Per-user dashboard. |
| `/projects` | Yes | List / create / delete projects. |
| `/projects/[id]` | Yes | Project detail. |
| `/admin` | Yes (`admin`) | Admin-gated placeholder. |
| `/api/auth/logout` | — | POST clears the session cookie. |
| `/api/health` | No | Liveness probe. |

## Safety

This example is for local development only. Sessions are signed cookies
(`HttpOnly`, `SameSite=Lax`), CSP / `X-Content-Type-Options` /
`X-Frame-Options` / `Referrer-Policy` headers are set in
`next.config.mjs`, and the middleware redirects unauthenticated users
to `/login` for any protected prefix.
