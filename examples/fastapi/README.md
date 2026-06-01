# SentinelQA FastAPI example

A small typed FastAPI app exposing a `Project` CRUD with auto-generated
OpenAPI. SentinelQA Phase 26.02.

This service is the backend for the Next.js (`examples/nextjs/`) and
React + Vite (`examples/react-vite/`) examples.

## Run

From the repo root:

```bash
make demo-fastapi
```

The Make target builds a throw-away virtualenv under
`examples/fastapi/.venv-demo/`, installs the pinned dependencies, and
starts `uvicorn` on `http://127.0.0.1:8000`.

Or, manually:

```bash
cd examples/fastapi
python -m venv .venv-demo
.venv-demo/bin/pip install -r requirements.txt
.venv-demo/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Credentials

A single demo bearer token is hard-coded for the local demo. **Do not
deploy this app**; the token is public:

```
Authorization: Bearer demo-token
```

Override it locally by exporting `SENTINEL_FASTAPI_TOKEN` before
booting the app.

## OpenAPI

The committed `openapi.json` is regenerated from the live app via:

```bash
make demo-fastapi-openapi
```

The audit pipeline reads it from `sentinel.config.yaml` (`api.openapi_path`).

## Audit it

With the app running:

```bash
sentinel api --url http://127.0.0.1:8000 --openapi examples/fastapi/openapi.json \ --config examples/fastapi/sentinel.config.yaml
```

The provided config sets `policy.min_quality_score: 85` and enables the
`contract`, `negative`, `auth`, and `error_shape` checks. A successful
run should report no critical findings.

## Routes

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/health` | No |
| `GET` | `/projects` | Yes |
| `POST` | `/projects` | Yes |
| `GET` | `/projects/{id}` | Yes |
| `PUT` | `/projects/{id}` | Yes |
| `DELETE` | `/projects/{id}` | Yes |

## Safety

This example is for local development only. CORS is restricted to the
local Next.js / Vite ports; auth is a fixed demo bearer token; no real
credential checking is performed.
