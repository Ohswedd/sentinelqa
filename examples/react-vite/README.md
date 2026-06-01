# SentinelQA React + Vite example

A Vite + React 18 SPA against the FastAPI demo backend. SentinelQA
Phase 26.05.

## Run

You need the FastAPI backend running on `http://127.0.0.1:8000` first
— see `examples/fastapi/README.md`.

Then from the repo root:

```bash
make demo-react-vite
```

The Make target runs `pnpm install` inside `examples/react-vite/` and
starts `vite` on `http://127.0.0.1:5173`.

Or, manually:

```bash
cd examples/react-vite
pnpm install
pnpm run dev
```

## Credentials

The SPA stores its session in React state only — refresh the page and
you have to log in again. Use the same demo bearer token the FastAPI
example documents:

| Username | Token |
| --- | --- |
| `demo` | `demo-token` |

## Audit it

With both apps running:

```bash
sentinel audit --url http://127.0.0.1:5173 \ --config examples/react-vite/sentinel.config.yaml
```

The provided config sets `discovery.engine: playwright` (the SPA's
routes are not in static HTML), enables `functional`, `accessibility`,
`performance`, `safe-security`, and `llm-audit`, and pins
`policy.min_quality_score: 85`.

## Routes

- `/` — landing page.
- `/login` — set the bearer token in React state.
- `/projects` — list / create / delete projects via the FastAPI backend.
- everything else → 404 page.

## Safety

The SPA never persists the bearer token. CORS is enforced on the
FastAPI side; both apps refuse to bind to anything but `127.0.0.1`.
