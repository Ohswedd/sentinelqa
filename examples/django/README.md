# SentinelQA Django example

A minimal Django 5 site with the built-in admin, a session-based login,
and a `Project` CRUD owned by the authenticated user. SentinelQA
Phase 26.03.

## Run

From the repo root:

```bash
make demo-django
```

The Make target builds a throw-away virtualenv under
`examples/django/.venv-demo/`, installs `Django==5.1.3`, applies
migrations against a SQLite file at `examples/django/demo.sqlite3`,
creates a `demo / demo` user if needed, and boots the dev server on
`http://127.0.0.1:8001`.

Or, manually:

```bash
cd examples/django
python -m venv .venv-demo
.venv-demo/bin/pip install -r requirements.txt
.venv-demo/bin/python manage.py migrate
.venv-demo/bin/python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
if not U.objects.filter(username='demo').exists():
    U.objects.create_user('demo', password='demo')
    U.objects.create_superuser('admin', '', 'admin')
"
.venv-demo/bin/python manage.py runserver 127.0.0.1:8001
```

## Credentials

Local demo only — **do not deploy this app**.

| Username | Password | Notes |
| --- | --- | --- |
| `demo` | `demo` | Project CRUD user. |
| `admin` | `admin` | Django admin superuser. |

## Audit it

With the app running:

```bash
sentinel audit --url http://127.0.0.1:8001 \
    --config examples/django/sentinel.config.yaml
```

The provided config sets `policy.min_quality_score: 85` and runs the
discovery / functional / accessibility / performance / safe-security /
llm-audit modules.

## Routes

- `GET /` — landing page.
- `GET /login/`, `POST /login/` — Django auth login.
- `POST /logout/` — clear the session cookie.
- `GET /projects/`, `POST /projects/` — list + create (auth required).
- `GET /projects/<id>/delete/` — delete confirm (auth required).
- `GET /admin/` — Django admin (superuser required).

## Safety

This example is for local development only. CSRF, X-Frame-Options,
HttpOnly cookies, and SameSite=Lax are enabled in `settings.py`. Debug
mode is off unless `SENTINEL_DJANGO_DEBUG=1` is exported.
