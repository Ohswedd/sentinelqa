# SentinelQA end-to-end demo

Ties the `examples/nextjs/` frontend and the `examples/fastapi/`
backend together with `docker compose`, then runs a full
`sentinel audit` against the stack. SentinelQA Phase 26.07.

## Run

From the repo root:

```bash
make demo
```

The `demo` Make target:

1. Boots `docker-compose.yml` from `examples/end-to-end-demo/` (FastAPI
   on `127.0.0.1:8000`, Next.js on `127.0.0.1:3000`).
2. Waits for the Next.js dev server to start serving HTTP.
3. Runs `sentinel audit --url http://127.0.0.1:3000 --config examples/nextjs/sentinel.config.yaml`.
4. Opens the generated HTML report in your default browser.

Tear down with:

```bash
make demo-down
```

## Acceptance

A full run should complete in under 10 minutes on a developer laptop.
The HTML report lives under `.sentinel/runs/<run-id>/report.html`; the
score is reproducible from the persisted `findings.json` + `score.json`.

## Layout

```
examples/end-to-end-demo/
├── docker-compose.yml   # FastAPI + Next.js services on the loopback interface
└── README.md            # this file
```

The compose file mounts the existing example directories read-only / RW
respectively rather than duplicating their code. Editing
`examples/nextjs/` while the compose stack is up will hot-reload the
Next.js dev server.

## Safety

- Both services bind to `127.0.0.1` only — never to a public interface.
- The FastAPI bearer token (`demo-token`) is the public demo value
  documented in `examples/fastapi/README.md`.
- `make demo` refuses to run `sentinel audit` against any host other
  than the local examples (the example `sentinel.config.yaml` only
  allows `127.0.0.1` / `localhost`).
