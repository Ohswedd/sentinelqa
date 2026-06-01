# SentinelQA LLM-broken example — DO NOT DEPLOY

A small Next.js 14 app that intentionally exhibits every the documentation
failure mode. The LLM-audit module (Phase 19) finds these issues; this
example exists so we can ship a one-command demo of that capability.

> ⚠️ **This app is intentionally broken.** Hardcoded credentials, mock
> data in production, frontend-only auth, dead buttons, and similar
> anti-patterns are deliberate. Do not deploy it. Do not copy patterns
> from it.

## Run

From the repo root:

```bash
make demo-llm-broken
```

The Make target runs `pnpm install` inside `examples/llm-broken/` and
starts the Next.js dev server on `http://127.0.0.1:3030`.

## Audit it

With the app running:

```bash
sentinel audit --url http://127.0.0.1:3030 \ --config examples/llm-broken/sentinel.config.yaml
```

A successful run produces ≥ 8 distinct LLM-audit findings:

| Rule | Where |
| --- | --- |
| `LLM-MOCK-DATA-SHIPPED` | `src/app/page.tsx` — `MOCK_ORDERS` rendered as if real. |
| `LLM-DEAD-BTN` | `src/app/page.tsx` and `src/app/checkout/page.tsx` — `Save` / `Place order` buttons have no handler. |
| `LLM-CONSOLE-ERROR-IGNORED` | `src/app/page.tsx` — error swallowed in inline script. |
| `LLM-HARDCODED-CRED` | `src/app/login/page.tsx` — `ADMIN_PASSWORD` literal. |
| `LLM-UI-ONLY-AUTH` | `src/app/login/page.tsx` and `src/app/admin/page.tsx` — token signed in browser; admin page does no role check. |
| `LLM-CLIENT-SECRET-STORAGE` | `src/app/login/page.tsx` — JWT in `localStorage`. |
| `LLM-NO-LOADING-STATE` / `LLM-NO-ERROR-STATE` / `LLM-UNHANDLED-PROMISE` | `src/app/dashboard/page.tsx` — `fetch` without `.catch`, no spinner, no error UI. |
| `LLM-FAKE-ENDPOINT` | `src/app/dashboard/page.tsx` calls `/api/orders`; no `app/api/orders/route.ts` exists. |
| `LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS` | `src/app/checkout/page.tsx` — email validated client-side only. |
| `LLM-PLACEHOLDER-TEXT` | `src/app/checkout/page.tsx` — "Coming soon" inside the live flow. |

## Safety

Same hard rules as the rest of the examples: binds to `127.0.0.1` only,
never to a public interface; no real credentials, no real payments, no
real data. The "admin" credentials in `login/page.tsx` are public and
local-only.
