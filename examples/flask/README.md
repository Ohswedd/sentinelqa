# SentinelQA Flask example

A minimal Flask 3.x app with cookie-based session auth and an in-memory
CRUD for the "Project" entity. SentinelQA Phase 26.04.

## Run

From the repo root:

```bash
make demo-flask
```

The Make target builds a throw-away virtualenv under
`examples/flask/.venv-demo/`, installs the pinned `Flask==3.0.3`
dependency, and boots `app.py` on `http://127.0.0.1:5001`.

Or, manually:

```bash
cd examples/flask
python -m venv .venv-demo
.venv-demo/bin/pip install -r requirements.txt
.venv-demo/bin/python app.py
```

## Credentials

A single demo user is hard-coded in `app.py` for the local demo. **Do
not deploy this app**; the credentials are public:

| Username | Password |
| --- | --- |
| `demo` | `demo` |

## Audit it

With the app running, point SentinelQA at it:

```bash
sentinel audit --url http://127.0.0.1:5001 --config examples/flask/sentinel.config.yaml
```

The provided config sets `policy.min_quality_score: 85` and runs the
discovery / functional / accessibility / performance / safe-security /
llm-audit modules. A successful run should report no critical findings.

## Routes

- `GET /` — landing page.
- `GET /login`, `POST /login` — session login form.
- `POST /logout` — clear the session cookie.
- `GET /projects` — list projects (auth required).
- `POST /projects` — create a project (auth required).
- `POST /projects/<id>/delete` — delete a project (auth required).
- `GET /health` — liveness probe.

## Safety

This example is for local development only. The session secret is
rotated per-process unless `SENTINEL_FLASK_SECRET` is set, cookies are
`HttpOnly` + `SameSite=Lax`, and basic security headers
(`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
`Content-Security-Policy`) are applied to every response.
