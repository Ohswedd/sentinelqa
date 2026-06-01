# examples/

Reference applications SentinelQA audits in its own CI and demos. PRD
§11.2, §27 (Example Generated Test), §32 (Recommended Build Order).
ships:

| Directory             | Stack                                                            | Boots on         | Run with               |
| --------------------- | ---------------------------------------------------------------- | ---------------- | ---------------------- |
| `nextjs/`             | Next.js 14 App Router, cookie session, in-memory CRUD            | `127.0.0.1:3000` | `make demo-nextjs`     |
| `fastapi/`            | FastAPI + Pydantic, Bearer auth, OpenAPI 3                       | `127.0.0.1:8000` | `make demo-fastapi`    |
| `django/`             | Django 5, session auth, admin, SQLite                            | `127.0.0.1:8001` | `make demo-django`     |
| `flask/`              | Flask 3, session auth, in-memory CRUD                            | `127.0.0.1:5001` | `make demo-flask`      |
| `react-vite/`         | Vite + React 18 SPA against `fastapi/`                           | `127.0.0.1:5173` | `make demo-react-vite` |
| `llm-broken/`         | Intentionally broken Next.js — drives the / 26.06 LLM-audit demo | `127.0.0.1:3030` | `make demo-llm-broken` |
| `end-to-end-demo/`    | `docker compose` stack tying `nextjs/` + `fastapi/` together     | `127.0.0.1:3000` | `make demo`            |
| `mcp-claude-desktop/` | Claude Desktop MCP config + walkthrough                          | —                | —                      |
| `plugins/`            | Reference plugins                                                | —                | —                      |

These exist so we can prove SentinelQA against real-world stacks before
any external user touches it. They are deliberately small and
well-known so failures are obvious.

Each example carries its own `sentinel.config.yaml` documenting the
audit profile (modules, gates, allowlists). The provided gates are
realistic: `policy.min_quality_score: 85` for the well-built apps,
`policy.min_quality_score: 0` for `llm-broken/` because its purpose is
to surface findings, not pass.

## Safety

Every example binds to `127.0.0.1` only — never to a public interface.
Every credential in the demo apps is public and documented in the
matching `README.md` (typically `demo / demo`). Do not deploy any of
these apps to a public host.
